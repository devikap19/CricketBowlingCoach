"""Quality endpoint tests use locally generated synthetic clips only."""

import json
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


@pytest.fixture
def quality_storage(monkeypatch):
    with tempfile.TemporaryDirectory(prefix="cbc-quality-test-", dir=Path(__file__).resolve().parents[2]) as temporary_directory:
        root = Path(temporary_directory)
        uploads = root / "uploads"
        sessions = root / "sessions"
        uploads.mkdir()
        sessions.mkdir()
        monkeypatch.setattr(settings, "upload_dir", str(uploads))
        monkeypatch.setattr(settings, "sessions_dir", str(sessions))
        yield uploads, sessions


def make_clip(path: Path, *, width=640, height=360, fps=30, frames=60, mode="normal"):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        pytest.skip("OpenCV MP4V writer is unavailable on this platform.")
    y, x = np.indices((height, width))
    if mode == "dark":
        frame = np.full((height, width, 3), 8, dtype=np.uint8)
    elif mode == "bright":
        frame = np.full((height, width, 3), 250, dtype=np.uint8)
    elif mode == "blurry":
        frame = np.full((height, width, 3), 120, dtype=np.uint8)
    else:
        pattern = (100 + ((x // 4 + y // 4) % 2) * 60).astype(np.uint8)
        frame = np.stack([pattern, pattern, pattern], axis=2)
    for index in range(frames):
        output = frame
        if mode == "normal":
            output = np.roll(frame, index % 5, axis=1)
        writer.write(output)
    writer.release()


def seed_session(quality_storage, session_id="11111111-1111-4111-8111-111111111111", *, video=True, mode="normal", width=640, height=360, fps=30, frames=60, metadata_override=None):
    uploads, sessions = quality_storage
    session_data = {
        "session_id": session_id,
        "bowler_name": "Synthetic Bowler",
        "session_date": "2026-11-04",
        "bowling_type": "fast",
        "bowling_arm": "right",
        "camera_view": "side",
        "notes": None,
        "original_filename": "clip.mp4",
        "video_size_bytes": 1,
        "status": "uploaded",
        "created_at": "2026-11-04T00:00:00Z",
    }
    if metadata_override is not None:
        (sessions / f"{session_id}.json").write_text(metadata_override, encoding="utf-8")
        return session_id
    (sessions / f"{session_id}.json").write_text(json.dumps(session_data), encoding="utf-8")
    if video:
        make_clip(uploads / f"{session_id}.mp4", width=width, height=height, fps=fps, frames=frames, mode=mode)
    return session_id


async def assess(client, session_id):
    return await client.post(f"/api/sessions/{session_id}/quality-check")


@pytest.mark.asyncio
async def test_valid_video_assessment(quality_storage):
    session_id = seed_session(quality_storage)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await assess(client, session_id)
        cached_response = await assess(client, session_id)
    assert response.status_code == 200
    data = response.json()
    assert data["overall_assessment"] in {"suitable", "suitable_with_limitations"}
    assert data["metadata"]["width"] == 640
    assert data["metadata"]["height"] == 360
    assert {metric["name"] for metric in data["metrics"]} >= {"Video integrity", "Resolution", "Frame rate", "Brightness and lighting", "Motion blur", "Camera stability", "Bowler visibility", "Pose coverage"}
    assert cached_response.json() == data
    assert (quality_storage[1] / f"{session_id}.quality.json").exists()


@pytest.mark.asyncio
async def test_corrupted_video_returns_not_suitable_assessment(quality_storage):
    session_id = seed_session(quality_storage, video=False)
    (quality_storage[0] / f"{session_id}.mp4").write_bytes(b"not a video")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await assess(client, session_id)
    assert response.status_code == 200
    assert response.json()["overall_assessment"] == "not_suitable"
    integrity = next(metric for metric in response.json()["metrics"] if metric["name"] == "Video integrity")
    assert integrity["status"] == "unavailable"


@pytest.mark.asyncio
async def test_missing_session(quality_storage):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await assess(client, "11111111-1111-4111-8111-111111111111")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_missing_video_file(quality_storage):
    session_id = seed_session(quality_storage, video=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await assess(client, session_id)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_invalid_session_metadata(quality_storage):
    session_id = seed_session(quality_storage, metadata_override="{broken json")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await assess(client, session_id)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_low_resolution_is_reported(quality_storage):
    session_id = seed_session(quality_storage, width=320, height=240)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await assess(client, session_id)
    resolution = next(metric for metric in response.json()["metrics"] if metric["name"] == "Resolution")
    assert resolution["value"]["classification"] == "below_initial_minimum"
    assert response.json()["overall_assessment"] == "not_suitable"


@pytest.mark.asyncio
async def test_low_frame_rate_is_reported(quality_storage):
    session_id = seed_session(quality_storage, fps=10)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await assess(client, session_id)
    metric = next(metric for metric in response.json()["metrics"] if metric["name"] == "Frame rate")
    assert metric["value"]["classification"] == "below_initial_minimum"
    assert response.json()["overall_assessment"] == "not_suitable"


@pytest.mark.asyncio
async def test_dark_video_is_reported(quality_storage):
    session_id = seed_session(quality_storage, mode="dark")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await assess(client, session_id)
    metric = next(metric for metric in response.json()["metrics"] if metric["name"] == "Brightness and lighting")
    assert metric["value"]["very_dark_pixel_percent"] > 90
    assert metric["recommendation"]


@pytest.mark.asyncio
async def test_overexposed_video_is_reported(quality_storage):
    session_id = seed_session(quality_storage, mode="bright")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await assess(client, session_id)
    metric = next(metric for metric in response.json()["metrics"] if metric["name"] == "Brightness and lighting")
    assert metric["value"]["very_bright_pixel_percent"] > 90
    assert metric["recommendation"]


@pytest.mark.asyncio
async def test_blurry_video_is_reported(quality_storage):
    session_id = seed_session(quality_storage, mode="blurry")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await assess(client, session_id)
    metric = next(metric for metric in response.json()["metrics"] if metric["name"] == "Motion blur")
    assert metric["value"]["lowest_laplacian_variance"] < settings.quality_min_blur_variance
    assert metric["recommendation"]


@pytest.mark.asyncio
async def test_insufficient_decodable_frames_mark_sampling_unavailable(quality_storage):
    session_id = seed_session(quality_storage, frames=2)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await assess(client, session_id)
    assert response.status_code == 200
    lighting = next(metric for metric in response.json()["metrics"] if metric["name"] == "Brightness and lighting")
    assert lighting["status"] == "unavailable"
    assert response.json()["overall_assessment"] == "not_suitable"
