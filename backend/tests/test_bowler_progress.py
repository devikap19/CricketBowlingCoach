"""Longitudinal bowler history API tests."""

import json
import tempfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


@pytest.fixture
def storage(monkeypatch):
    with tempfile.TemporaryDirectory(prefix="cbc-progress-test-", dir=Path(__file__).resolve().parents[2]) as temporary:
        base = Path(temporary)
        monkeypatch.setattr(settings, "sessions_dir", str(base / "sessions"))
        monkeypatch.setattr(settings, "upload_dir", str(base / "uploads"))
        monkeypatch.setattr(settings, "max_upload_size_bytes", 1024)
        yield base


def upload_fields(name="Asha Kumar", date="2026-11-01"):
    return {
        "bowler_name": name,
        "session_date": date,
        "bowling_type": "fast",
        "bowling_arm": "right",
        "camera_view": "front",
    }


def tiny_video():
    return {"video": ("practice.mp4", b"\x00\x00\x00\x18ftypisom", "video/mp4")}


@pytest.mark.asyncio
async def test_bowler_progress_returns_all_sessions_and_saved_measurements(storage):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/sessions", data=upload_fields(date="2026-11-01"), files=tiny_video())
        second = await client.post("/api/sessions", data=upload_fields(name="ASHA KUMAR", date="2026-11-03"), files=tiny_video())

        for response, median in ((first, 18.2), (second, 9.4)):
            sid = response.json()["session_id"]
            (storage / "sessions" / f"{sid}.pose.json").write_text(json.dumps({
                "pose_validation_status": "valid",
                "detected_frame_count": 10,
                "sampled_frame_count": 12,
                "biomechanics": {
                    "summary": {
                        "shoulder_line_tilt": {
                            "median": median, "min": 2.0, "max": 22.0,
                            "valid_frames": 10, "sampled_frames": 12,
                        }
                    },
                    "frames": [
                        {"frame_number": 1, "timestamp_seconds": 0.5,
                         "measurements": {"shoulder_line_tilt": {"value": median}}}
                    ],
                },
            }), encoding="utf-8")

        response = await client.get("/api/bowlers/progress", params={"bowler_name": "Asha Kumar"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["sessions"]) == 2
    assert payload["sessions"][0]["session"]["session_id"] == first.json()["session_id"]
    assert payload["sessions"][1]["biomechanics_summary"]["shoulder_line_tilt"]["median"] == 9.4
    assert "path" not in json.dumps(payload).lower()


@pytest.mark.asyncio
async def test_bowler_progress_does_not_mix_different_bowlers(storage):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/sessions", data=upload_fields(name="Asha Kumar"), files=tiny_video())
        await client.post("/api/sessions", data=upload_fields(name="Riya Shah"), files=tiny_video())
        response = await client.get("/api/bowlers/progress", params={"bowler_name": "Asha Kumar"})
    assert response.status_code == 200
    assert len(response.json()["sessions"]) == 1
    assert response.json()["sessions"][0]["session"]["bowler_name"] == "Asha Kumar"
