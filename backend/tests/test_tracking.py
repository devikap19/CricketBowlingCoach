"""Coach-assisted tracking and delivery interval tests."""

from pathlib import Path

import cv2
import numpy as np
import pytest
import json
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.pose.subject_tracking import track_selected_subject
from app.pose.tracking_models import SubjectSelection


def make_tracking_video(path: Path, frames: int = 70, fps: int = 10):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (320, 240))
    if not writer.isOpened():
        pytest.skip("OpenCV MP4V writer is unavailable on this platform.")
    for index in range(frames):
        frame = np.full((240, 320, 3), 30, dtype=np.uint8)
        # Static background player: a different appearance must never be adopted after loss.
        cv2.rectangle(frame, (235, 60), (280, 220), (220, 40, 30), -1)
        cv2.rectangle(frame, (235, 60), (280, 220), (255, 255, 255), 2)
        for y in range(70, 210, 12):
            cv2.line(frame, (238, y), (277, y), (160, 200, 255), 2)
        x = 20 + index * 5
        if x < 320:
            cv2.rectangle(frame, (x, 40), (x+42, 210), (30, 160, 40), -1)
            cv2.rectangle(frame, (x, 40), (x+42, 210), (255, 255, 255), 2)
            for y in range(50, 205, 12):
                cv2.line(frame, (x+4, y), (x+38, y), (210, 255, 220), 2)
        writer.write(frame)
    writer.release()


@pytest.fixture
def api_storage(tmp_path, monkeypatch):
    uploads, sessions, processed = tmp_path / "uploads", tmp_path / "sessions", tmp_path / "processed"
    for path in (uploads, sessions, processed):
        path.mkdir()
    monkeypatch.setattr(settings, "upload_dir", str(uploads))
    monkeypatch.setattr(settings, "sessions_dir", str(sessions))
    monkeypatch.setattr(settings, "processed_dir", str(processed))
    return uploads, sessions


def test_selected_subject_tracking_does_not_reacquire_another_person(tmp_path):
    video = tmp_path / "two_subjects.mp4"
    make_tracking_video(video)
    result = track_selected_subject(
        "session", video,
        SubjectSelection(timestamp_seconds=0, box={"x": .06, "y": .15, "width": .15, "height": .72}),
    )
    assert result.selection_status == "coach_selected"
    assert result.sampled_track_count > 10
    assert result.tracking_interruptions
    first_lost = next((index for index, point in enumerate(result.track) if point.status in ("lost", "outside_frame")), None)
    if first_lost is not None:
        assert all(point.status in ("lost", "outside_frame") for point in result.track[first_lost:])
    # The red static player remains in-frame after the selected green subject exits.
    assert result.tracked_sample_count < result.sampled_track_count


def test_selected_subject_history_proposes_moving_interval(tmp_path):
    video = tmp_path / "runup.mp4"
    make_tracking_video(video, frames=50)
    result = track_selected_subject(
        "session", video,
        SubjectSelection(timestamp_seconds=0, box={"x": .06, "y": .15, "width": .15, "height": .72}),
    )
    assert result.proposed_intervals
    interval = result.proposed_intervals[0]
    assert interval.start_seconds < interval.end_seconds
    assert interval.end_seconds <= result.duration_seconds


def test_original_bowling_video_preserves_observed_scale_adaptation():
    """Regression check against the reviewed Stage 4 bowling1.mp4 run."""
    project_root = Path(__file__).resolve().parents[2]
    session_id = "b3e5ec96-711b-46d4-90b7-bffcaa6f6b9a"
    video = project_root / "storage" / "uploads" / f"{session_id}.mp4"
    saved_path = project_root / "storage" / "sessions" / f"{session_id}.tracking.json"
    if not video.is_file() or not saved_path.is_file():
        pytest.skip("The reviewed original bowling video is not available in this checkout.")
    saved = json.loads(saved_path.read_text(encoding="utf-8"))
    # Preserve the reviewed result as a baseline, including its large approach
    # expansion (which should be reviewed for background inclusion, not clamped).
    for timestamp, expected_width in ((2.5, .186), (3.5, .406), (4.0, .478)):
        saved_point = min(saved["track"], key=lambda item: abs(item["timestamp_seconds"]-timestamp))
        assert abs(saved_point["timestamp_seconds"]-timestamp) <= .15
        assert saved_point["box"]["width"] == pytest.approx(expected_width, abs=.01)
    result = track_selected_subject(
        session_id,
        video,
        SubjectSelection(timestamp_seconds=saved["selected_at_seconds"], box=saved["selected_box"]),
    )

    def nearest_width(timestamp):
        point = min(result.track, key=lambda item: abs(item.timestamp_seconds-timestamp))
        assert abs(point.timestamp_seconds-timestamp) <= .15
        assert point.box is not None and point.status == "tracked"
        return point.box.width

    # MIL/optical-flow outputs vary between runs. Verify adaptive expansion
    # without requiring the run to reproduce a particular box size.
    assert nearest_width(3.5) >= nearest_width(2.5) * 1.5


@pytest.mark.asyncio
async def test_tracking_api_and_manual_interval_confirmation(api_storage):
    uploads, sessions = api_storage
    session_id = "44444444-4444-4444-8444-444444444444"
    (sessions / f"{session_id}.json").write_text(json.dumps({"session_id":session_id,"original_filename":"sample.mp4"}),encoding="utf-8")
    make_tracking_video(uploads / f"{session_id}.mp4", frames=50)
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as client:
        preview = await client.get(f"/api/sessions/{session_id}/video")
        range_preview = await client.get(f"/api/sessions/{session_id}/video",headers={"Range":"bytes=0-31"})
        tracked = await client.post(f"/api/sessions/{session_id}/subject-tracking",json={
            "timestamp_seconds":0,"box":{"x":.06,"y":.15,"width":.15,"height":.72}})
        saved_tracking = await client.get(f"/api/sessions/{session_id}/subject-tracking")
        assert tracked.status_code == 200, tracked.text
        first_frame = tracked.json()["track"][0]["frame_number"]
        review = await client.get(f"/api/sessions/{session_id}/subject-tracking-preview/{first_frame}")
        coach_review = await client.get(f"/api/sessions/{session_id}/subject-tracking-preview/{first_frame}?coach_facing=true")
        confirmed = await client.post(f"/api/sessions/{session_id}/subject-interval",json={"start_seconds":0,"end_seconds":2})
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "video/mp4"
    assert range_preview.status_code == 206
    assert range_preview.headers["content-range"] == "bytes 0-31/" + str(len((uploads/f"{session_id}.mp4").read_bytes()))
    assert tracked.json()["selection_status"] == "coach_selected"
    assert saved_tracking.status_code == 200
    assert saved_tracking.json()["session_id"] == session_id
    assert saved_tracking.json()["track"] == tracked.json()["track"]
    assert review.status_code == 200
    assert review.headers["content-type"] == "image/jpeg"
    assert coach_review.status_code == 200
    assert coach_review.headers["content-type"] == "image/jpeg"
    rendered = cv2.imdecode(np.frombuffer(review.content, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert rendered is not None and rendered.shape[:2] == (240, 320)
    assert tracked.json()["track"][0]["feature_count"] == 0
    assert "optical-flow" in tracked.json()["scale_estimation_method"]
    assert tracked.json()["identity_validation_status"] == "not_independently_verified"
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["interval_source"] == "manual"
    assert confirmed.json()["confirmed_interval"]["start_seconds"] == 0

