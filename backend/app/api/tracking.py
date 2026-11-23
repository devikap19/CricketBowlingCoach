"""Video preview, coach-selected subject tracking, and interval confirmation."""

import json
import uuid
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.pose.subject_tracking import track_selected_subject
from app.pose.tracking_models import ActiveInterval, SubjectSelection, TrackingAssessment

router = APIRouter()


def _session_paths(session_id: str) -> tuple[Path, Path, Path]:
    try:
        normalized = str(uuid.UUID(session_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Session not found.") from None
    sessions = Path(settings.sessions_dir).resolve()
    metadata_path = sessions / f"{normalized}.json"
    if metadata_path.resolve().parent != sessions or not metadata_path.is_file():
        raise HTTPException(status_code=404, detail="Session not found.")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        ext = Path(str(metadata.get("original_filename", ""))).suffix.lower()
        if metadata.get("session_id") != normalized or ext not in {".mp4", ".mov"}:
            raise ValueError
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=422, detail="Session metadata is invalid.") from None
    uploads = Path(settings.upload_dir).resolve()
    video = (uploads / f"{normalized}{ext}").resolve()
    if video.parent != uploads or not video.is_file():
        raise HTTPException(status_code=404, detail="Session video not found.")
    return normalized, sessions, video


class IntervalReview(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)


@router.get("/sessions/{session_id}/video", include_in_schema=False)
async def get_session_video(session_id: str):
    _, _, video = _session_paths(session_id)
    media = "video/mp4" if video.suffix.lower() == ".mp4" else "video/quicktime"
    return FileResponse(video, media_type=media, filename=None, content_disposition_type="inline")


@router.get("/sessions/{session_id}/subject-tracking", response_model=TrackingAssessment)
async def get_subject_tracking(session_id: str) -> TrackingAssessment:
    """Return a previously saved tracking result for session workspace navigation."""
    normalized, sessions, _ = _session_paths(session_id)
    tracking_path = sessions / f"{normalized}.tracking.json"
    if tracking_path.resolve().parent != sessions or not tracking_path.is_file():
        raise HTTPException(status_code=404, detail="Tracking result not found.")
    try:
        tracking = TrackingAssessment.model_validate_json(tracking_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise HTTPException(status_code=422, detail="The saved tracking result is invalid.") from None
    if tracking.session_id != normalized:
        raise HTTPException(status_code=422, detail="The saved tracking result does not match this session.")
    return tracking


@router.get("/sessions/{session_id}/subject-tracking-preview/{frame_number}", include_in_schema=False)
async def get_subject_tracking_preview(session_id: str, frame_number: int, coach_facing: bool = Query(default=False)):
    """Render one saved tracker box directly over its original decoded video frame."""
    normalized, sessions, video = _session_paths(session_id)
    tracking_path = sessions / f"{normalized}.tracking.json"
    if tracking_path.resolve().parent != sessions or not tracking_path.is_file():
        raise HTTPException(status_code=404, detail="Tracking preview not found.")
    try:
        tracking = TrackingAssessment.model_validate_json(tracking_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(status_code=404, detail="Tracking preview not found.") from None
    point = next((sample for sample in tracking.track if sample.frame_number == frame_number), None)
    if point is None:
        raise HTTPException(status_code=404, detail="No saved tracking sample exists at that frame.")
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise HTTPException(status_code=422, detail="The saved video could not be opened.")
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ok, frame = capture.read()
    finally:
        capture.release()
    if not ok or frame is None:
        raise HTTPException(status_code=404, detail="The original video frame could not be decoded.")
    height, width = frame.shape[:2]
    color = (0, 190, 255) if point.status != "tracked" else (0, 165, 255)
    if point.box is not None:
        x1 = max(0, min(width-1, round(point.box.x*width)))
        y1 = max(0, min(height-1, round(point.box.y*height)))
        x2 = max(x1+1, min(width-1, round((point.box.x+point.box.width)*width)))
        y2 = max(y1+1, min(height-1, round((point.box.y+point.box.height)*height)))
        cv2.rectangle(frame, (x1,y1), (x2,y2), color, max(2, round(width/240)))
        box_label = f"Box {point.box.width*100:.1f}% x {point.box.height*100:.1f}%"
    else:
        box_label = "No box available"
    if coach_facing:
        label = "Selected bowler" if point.status == "tracked" and point.box is not None else "Review selection"
    else:
        distance_label = "unavailable" if point.appearance_distance is None else f"{point.appearance_distance:.3f}"
        label = f"{point.timestamp_seconds:.2f}s | MIL {point.status} | HSV distance {distance_label} | {box_label}"
    cv2.rectangle(frame, (0,0), (width,36), (0,0,0), -1)
    cv2.putText(frame, label[:110], (8,24), cv2.FONT_HERSHEY_SIMPLEX, .55, (255,255,255), 1, cv2.LINE_AA)
    success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not success or not np.isfinite(frame).all():
        raise HTTPException(status_code=500, detail="The tracking review frame could not be rendered.")
    return Response(encoded.tobytes(), media_type="image/jpeg", headers={"Cache-Control":"no-store"})


@router.post("/sessions/{session_id}/subject-tracking", response_model=TrackingAssessment)
async def start_subject_tracking(session_id: str, selection: SubjectSelection) -> TrackingAssessment:
    normalized, sessions, video = _session_paths(session_id)
    if selection.box.x + selection.box.width > 1 or selection.box.y + selection.box.height > 1:
        raise HTTPException(status_code=422, detail="The selection box must stay within the video frame.")
    try:
        result = await run_in_threadpool(track_selected_subject, normalized, video, selection)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=422, detail="Subject tracking could not be completed for this video.") from error
    path = sessions / f"{normalized}.tracking.json"
    temporary = sessions / f".{normalized}.{uuid.uuid4().hex}.tracking.part"
    try:
        temporary.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Tracking result could not be saved.") from error
    return result


@router.post("/sessions/{session_id}/subject-interval", response_model=TrackingAssessment)
async def confirm_subject_interval(session_id: str, review: IntervalReview) -> TrackingAssessment:
    normalized, sessions, _ = _session_paths(session_id)
    path = sessions / f"{normalized}.tracking.json"
    if path.resolve().parent != sessions or not path.is_file():
        raise HTTPException(status_code=409, detail="Select and track the bowler before confirming an interval.")
    try:
        tracking = TrackingAssessment.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(status_code=409, detail="The saved tracking result is invalid. Track the bowler again.") from None
    if review.start_seconds >= review.end_seconds or review.end_seconds > tracking.duration_seconds:
        raise HTTPException(status_code=422, detail="Choose a valid interval inside the video duration.")
    if review.start_seconds < tracking.selected_at_seconds:
        raise HTTPException(status_code=422, detail="The interval cannot begin before the frame where the bowler was selected.")
    if not any(point.status == "tracked" and review.start_seconds <= point.timestamp_seconds <= review.end_seconds for point in tracking.track):
        raise HTTPException(status_code=422, detail="The interval contains no reliably tracked bowler frames.")
    match = next((candidate for candidate in tracking.proposed_intervals
                  if abs(candidate.start_seconds-review.start_seconds) < .05 and abs(candidate.end_seconds-review.end_seconds) < .05), None)
    tracking.confirmed_interval = match or ActiveInterval(start_seconds=review.start_seconds, end_seconds=review.end_seconds,
        confidence="medium", reason="Interval adjusted and confirmed by coach.")
    tracking.interval_source = "automatic" if match else "manual"
    tracking.active_frame_count = sum(review.start_seconds <= point.timestamp_seconds <= review.end_seconds for point in tracking.track)
    tracking.excluded_idle_frame_count = sum(point.timestamp_seconds < review.start_seconds or point.timestamp_seconds > review.end_seconds for point in tracking.track)
    temporary = sessions / f".{normalized}.{uuid.uuid4().hex}.tracking.part"
    try:
        temporary.write_text(tracking.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="The interval confirmation could not be saved.") from error
    # An interval change invalidates any previous pose coverage.
    (sessions / f"{normalized}.pose.json").unlink(missing_ok=True)
    return tracking

