"""Pose assessment and safe preview image endpoints."""

import json
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.biomechanics.engine import analyse_front_view
from app.pose.browser_pose import BrowserPoseCrop, BrowserPoseSubmission
from app.pose.browser_pose_service import (
    BrowserPosePreparationError,
    prepare_browser_pose_crops,
)
from app.pose.pose_extraction import VideoSamplingError, extract_pose_assessment
from app.pose.pose_models import PoseAssessment
from app.pose.tracking_models import TrackingAssessment
from app.video.quality_models import QualityAssessment

router = APIRouter()
ALLOWED_EXTENSIONS = {".mp4", ".mov"}
FRAME_NAME = re.compile(r"^frame_\d{8}_(?:original|pose)\.jpg$")
BROWSER_CROP_NAME = re.compile(r"^frame_\d{8}\.jpg$")


def _session_id(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Session not found.") from None


def _load_pose_context(session_id: str):
    """Load and validate session, video, quality, and confirmed tracking data."""
    normalized_id = _session_id(session_id)
    sessions_dir = Path(settings.sessions_dir).resolve()
    metadata_path = sessions_dir / f"{normalized_id}.json"
    if metadata_path.resolve().parent != sessions_dir or not metadata_path.is_file():
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        session_data = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(session_data, dict) or session_data.get("session_id") != normalized_id:
            raise ValueError
        extension = Path(str(session_data.get("original_filename", ""))).suffix.lower()
        if (
            extension not in ALLOWED_EXTENSIONS
            or session_data.get("camera_view") not in {"front", "side", "rear", "other"}
        ):
            raise ValueError
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Session metadata is invalid.") from None

    upload_dir = Path(settings.upload_dir).resolve()
    video_path = (upload_dir / f"{normalized_id}{extension}").resolve()
    if video_path.parent != upload_dir:
        raise HTTPException(status_code=422, detail="Session video location is invalid.")
    if not video_path.is_file():
        raise HTTPException(status_code=404, detail="Session video file not found.")

    quality_path = sessions_dir / f"{normalized_id}.quality.json"
    if quality_path.resolve().parent != sessions_dir or not quality_path.is_file():
        raise HTTPException(
            status_code=409,
            detail="Run the technical video quality check before pose assessment.",
        )
    try:
        quality = QualityAssessment.model_validate_json(
            quality_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, ValidationError, ValueError):
        raise HTTPException(
            status_code=409,
            detail="The saved video quality check is invalid; run it again first.",
        ) from None

    integrity = next(
        (metric for metric in quality.metrics if metric.name == "Video integrity"),
        None,
    )
    if (
        quality.session_id != normalized_id
        or integrity is None
        or integrity.status != "reliable"
        or not isinstance(integrity.value, dict)
        or not integrity.value.get("opened")
        or not integrity.value.get("decodable_sample_frames")
    ):
        raise HTTPException(
            status_code=422,
            detail="The video has not passed the technical integrity check.",
        )

    tracking_path = sessions_dir / f"{normalized_id}.tracking.json"
    if tracking_path.resolve().parent != sessions_dir or not tracking_path.is_file():
        raise HTTPException(
            status_code=409,
            detail="Select and track the bowler, then confirm the active interval before pose assessment.",
        )
    try:
        tracking = TrackingAssessment.model_validate_json(
            tracking_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, ValueError, ValidationError):
        raise HTTPException(
            status_code=409,
            detail="The saved tracking result is invalid; track the bowler again.",
        ) from None

    if tracking.session_id != normalized_id or tracking.confirmed_interval is None:
        raise HTTPException(
            status_code=409,
            detail="Confirm the active interval before pose assessment.",
        )

    return normalized_id, sessions_dir, session_data, video_path, tracking


@router.get(
    "/sessions/{session_id}/pose-assessment",
    response_model=PoseAssessment,
)
async def get_saved_pose_assessment(session_id: str) -> PoseAssessment:
    """Load a previously saved pose assessment without rerunning MoveNet."""
    normalized_id = _session_id(session_id)
    sessions_dir = Path(settings.sessions_dir).resolve()
    metadata_path = (sessions_dir / f"{normalized_id}.json").resolve()
    assessment_path = (sessions_dir / f"{normalized_id}.pose.json").resolve()
    if (
        metadata_path.parent != sessions_dir
        or assessment_path.parent != sessions_dir
        or not metadata_path.is_file()
        or not assessment_path.is_file()
    ):
        raise HTTPException(status_code=404, detail="Saved pose assessment not found.")
    try:
        assessment = PoseAssessment.model_validate_json(
            assessment_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, ValueError, ValidationError):
        raise HTTPException(status_code=409, detail="Saved pose assessment is invalid.") from None
    if assessment.session_id != normalized_id:
        raise HTTPException(status_code=409, detail="Saved pose assessment does not match this session.")
    if not assessment.biomechanics or assessment.biomechanics.get("measurement_version") != 2:
        assessment.biomechanics = analyse_front_view(assessment)
        temporary_path = sessions_dir / f".{normalized_id}.{uuid.uuid4().hex}.pose.part"
        try:
            temporary_path.write_text(assessment.model_dump_json(indent=2), encoding="utf-8")
            temporary_path.replace(assessment_path)
        except OSError as error:
            temporary_path.unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail="Updated pose assessment could not be saved.") from error
    return assessment


@router.get(
    "/sessions/{session_id}/browser-pose-crops",
    response_model=list[BrowserPoseCrop],
)
async def get_browser_pose_crops(session_id: str) -> list[BrowserPoseCrop]:
    """Prepare tracked bowler crops for TensorFlow.js MoveNet in the browser."""
    normalized_id, _sessions_dir, session_data, video_path, tracking = _load_pose_context(
        session_id
    )
    processed_dir = Path(settings.processed_dir).resolve()
    session_dir = (processed_dir / normalized_id).resolve()
    crop_dir = (session_dir / "browser-pose-crops").resolve()
    if session_dir.parent != processed_dir or crop_dir.parent != session_dir:
        raise HTTPException(status_code=422, detail="Browser crop storage location is invalid.")

    try:
        crops = await run_in_threadpool(
            prepare_browser_pose_crops,
            normalized_id,
            video_path,
            crop_dir,
            tracking,
            f"/api/sessions/{normalized_id}/browser-pose-crops",
        )
    except BrowserPosePreparationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=422,
            detail="Bowler crops could not be prepared for browser pose inference.",
        ) from error

    return crops


@router.get(
    "/sessions/{session_id}/browser-pose-crops/{filename}",
    include_in_schema=False,
)
async def get_browser_pose_crop(session_id: str, filename: str):
    """Serve one prepared crop image to the browser."""
    normalized_id = _session_id(session_id)
    if not BROWSER_CROP_NAME.fullmatch(filename):
        raise HTTPException(status_code=404, detail="Browser crop image not found.")

    processed_dir = Path(settings.processed_dir).resolve()
    session_dir = (processed_dir / normalized_id).resolve()
    crop_dir = (session_dir / "browser-pose-crops").resolve()
    image_path = (crop_dir / filename).resolve()
    if (
        session_dir.parent != processed_dir
        or crop_dir.parent != session_dir
        or image_path.parent != crop_dir
        or not image_path.is_file()
    ):
        raise HTTPException(status_code=404, detail="Browser crop image not found.")
    return FileResponse(image_path, media_type="image/jpeg")


@router.post("/sessions/{session_id}/pose-assessment", response_model=PoseAssessment)
async def assess_session_pose(
    session_id: str,
    payload: BrowserPoseSubmission | None = Body(default=None),
    refresh: bool = Query(
        default=False,
        description="Recalculate and replace a previously saved pose assessment.",
    ),
) -> PoseAssessment:
    (
        normalized_id,
        sessions_dir,
        session_data,
        video_path,
        tracking,
    ) = _load_pose_context(session_id)

    assessment_path = sessions_dir / f"{normalized_id}.pose.json"
    if assessment_path.resolve().parent != sessions_dir:
        raise HTTPException(
            status_code=422,
            detail="Pose assessment storage location is invalid.",
        )

    if assessment_path.is_file() and not refresh:
        try:
            cached = PoseAssessment.model_validate_json(
                assessment_path.read_text(encoding="utf-8")
            )
            processed_dir = Path(settings.processed_dir).resolve()
            cached_dir = (processed_dir / normalized_id).resolve()
            previews_exist = cached_dir.parent == processed_dir and all(
                frame.original_image_url
                == f"/api/sessions/{normalized_id}/pose-frames/frame_{frame.frame_number:08d}_original.jpg"
                and frame.overlay_image_url
                == f"/api/sessions/{normalized_id}/pose-frames/frame_{frame.frame_number:08d}_pose.jpg"
                and (cached_dir / f"frame_{frame.frame_number:08d}_original.jpg").is_file()
                and (cached_dir / f"frame_{frame.frame_number:08d}_pose.jpg").is_file()
                for frame in cached.frames
            )
            diagnostics_exist = bool(cached.frames) and all(
                frame.crop_diagnostics is not None for frame in cached.frames
            )
            tracking_matches_cache = bool(
                cached.tracking
                and cached.tracking.confirmed_interval == tracking.confirmed_interval
                and cached.tracking.track == tracking.track
            )
            if (
                cached.session_id == normalized_id
                and cached.validation_schema_version >= 2
                and cached.camera_view == session_data.get("camera_view", "other")
                and previews_exist
                and diagnostics_exist
                and tracking_matches_cache
            ):
                if not cached.biomechanics or cached.biomechanics.get("measurement_version") != 2:
                    cached.biomechanics = analyse_front_view(cached)
                    assessment_path.write_text(cached.model_dump_json(indent=2), encoding="utf-8")
                return cached
        except (OSError, UnicodeError, ValidationError, ValueError):
            pass

    if payload is None:
        raise HTTPException(
            status_code=422,
            detail="Browser pose predictions are required.",
        )

    processed_dir = Path(settings.processed_dir).resolve()
    output_dir = (processed_dir / normalized_id).resolve()
    if output_dir.parent != processed_dir:
        raise HTTPException(
            status_code=422,
            detail="Pose preview storage location is invalid.",
        )

    base_url = f"/api/sessions/{normalized_id}/pose-frames"
    try:
        crop_dir = (output_dir / "browser-pose-crops").resolve()
        if crop_dir.parent != output_dir:
            raise HTTPException(
                status_code=422,
                detail="Browser crop storage location is invalid.",
            )
        crops = await run_in_threadpool(
            prepare_browser_pose_crops,
            normalized_id,
            video_path,
            crop_dir,
            tracking,
            f"/api/sessions/{normalized_id}/browser-pose-crops",
        )
        expected = {crop.frame_number: crop.timestamp_seconds for crop in crops}
        submitted = {frame.frame_number: frame for frame in payload.frames}
        if not set(submitted).issubset(set(expected)):
            raise HTTPException(
                status_code=422,
                detail="Submitted browser predictions contain frames that were not prepared for this session.",
            )
        for frame_number, prediction in submitted.items():
            timestamp = expected[frame_number]
            if abs(prediction.timestamp_seconds - timestamp) > 0.002:
                raise HTTPException(
                    status_code=422,
                    detail=f"Timestamp does not match the prepared crop for frame {frame_number}.",
                )

        browser_predictions = {
            frame.frame_number: [
                point.model_dump() for point in frame.keypoints
            ]
            for frame in payload.frames
        }
        result = await run_in_threadpool(
            extract_pose_assessment,
            normalized_id,
            video_path,
            output_dir,
            base_url,
            tracking,
            session_data.get("camera_view", "other"),
            browser_predictions,
        )
    except BrowserPosePreparationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except VideoSamplingError as error:
        raise HTTPException(
            status_code=422,
            detail="The video contains no usable sampled frames.",
        ) from error
    except (ValueError, OSError) as error:
        raise HTTPException(
            status_code=422,
            detail="Pose assessment could not be completed for this video.",
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail="Pose inference is currently unavailable.",
        ) from error

    result.biomechanics = analyse_front_view(result)

    temporary_path = sessions_dir / f".{normalized_id}.{uuid.uuid4().hex}.pose.part"
    try:
        temporary_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        temporary_path.replace(assessment_path)
    except OSError as error:
        temporary_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail="Pose assessment could not be saved.",
        ) from error
    return result


@router.get(
    "/sessions/{session_id}/pose-frames/{filename}",
    include_in_schema=False,
)
async def get_pose_frame(session_id: str, filename: str):
    normalized_id = _session_id(session_id)
    if not FRAME_NAME.fullmatch(filename):
        raise HTTPException(status_code=404, detail="Preview image not found.")

    processed_dir = Path(settings.processed_dir).resolve()
    session_dir = (processed_dir / normalized_id).resolve()
    image_path = (session_dir / filename).resolve()
    if (
        session_dir.parent != processed_dir
        or image_path.parent != session_dir
        or not image_path.is_file()
    ):
        raise HTTPException(status_code=404, detail="Preview image not found.")
    return FileResponse(image_path, media_type="image/jpeg")
