"""Video quality assessment endpoint for saved sessions."""

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.video.quality_assessment import assess_video
from app.video.quality_models import QualityAssessment

router = APIRouter()
ALLOWED_EXTENSIONS = {".mp4", ".mov"}


@router.post("/sessions/{session_id}/quality-check", response_model=QualityAssessment)
async def check_session_quality(
    session_id: str,
    refresh: bool = Query(default=False, description="Recalculate and replace a previously saved assessment."),
) -> QualityAssessment:
    try:
        normalized_id = str(uuid.UUID(session_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Session not found.") from None

    sessions_dir = Path(settings.sessions_dir).resolve()
    metadata_path = sessions_dir / f"{normalized_id}.json"
    if metadata_path.resolve().parent != sessions_dir or not metadata_path.is_file():
        raise HTTPException(status_code=404, detail="Session not found.")
    try:
        session_data = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(session_data, dict) or session_data.get("session_id") != normalized_id:
            raise ValueError("Session metadata does not match its identifier.")
        extension = Path(str(session_data.get("original_filename", ""))).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS or session_data.get("camera_view") not in {"front", "side", "rear", "other"}:
            raise ValueError("Session metadata does not contain a supported video extension.")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Session metadata is invalid.") from None

    upload_dir = Path(settings.upload_dir).resolve()
    video_path = (upload_dir / f"{normalized_id}{extension}").resolve()
    if video_path.parent != upload_dir:
        raise HTTPException(status_code=422, detail="Session video location is invalid.")
    if not video_path.is_file():
        raise HTTPException(status_code=404, detail="Session video file not found.")

    assessment_path = sessions_dir / f"{normalized_id}.quality.json"
    if assessment_path.resolve().parent != sessions_dir:
        raise HTTPException(status_code=422, detail="Assessment storage location is invalid.")
    if assessment_path.is_file() and not refresh:
        try:
            cached = QualityAssessment.model_validate_json(assessment_path.read_text(encoding="utf-8"))
            if cached.session_id == normalized_id:
                return cached
        except (OSError, UnicodeError, ValueError):
            # Invalid cache is recalculated and replaced below.
            pass

    try:
        assessment = await run_in_threadpool(assess_video, normalized_id, video_path, str(session_data.get("camera_view", "other")))
    except Exception as error:
        raise HTTPException(status_code=422, detail="Video could not be assessed.") from error

    temporary_path = sessions_dir / f".{normalized_id}.{uuid.uuid4().hex}.quality.part"
    try:
        temporary_path.write_text(assessment.model_dump_json(indent=2), encoding="utf-8")
        temporary_path.replace(assessment_path)
    except OSError as error:
        temporary_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Quality assessment could not be saved.") from error
    return assessment
