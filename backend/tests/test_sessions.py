"""Tests for session creation and video upload."""

import pytest
import tempfile
from pathlib import Path
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


@pytest.fixture
def storage(monkeypatch):
    with tempfile.TemporaryDirectory(prefix="cbc-test-", dir=Path(__file__).resolve().parents[2]) as temporary_directory:
        root = Path(temporary_directory)
        monkeypatch.setattr(settings, "upload_dir", str(root / "uploads"))
        monkeypatch.setattr(settings, "sessions_dir", str(root / "sessions"))
        monkeypatch.setattr(settings, "max_upload_size_bytes", 32)
        yield root


def fields(**overrides):
    values = {
        "bowler_name": "Asha Kumar",
        "session_date": "2026-11-04",
        "bowling_type": "fast",
        "bowling_arm": "right",
        "camera_view": "side",
        "notes": "Practice session",
    }
    values.update(overrides)
    return values


def video(name="practice.mp4", content=b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00"):
    return {"video": (name, content, "video/mp4")}


@pytest.mark.asyncio
async def test_successful_video_upload(storage):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/sessions", data=fields(), files=video())
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "uploaded"
    assert data["bowler_name"] == "Asha Kumar"
    assert data["video_size_bytes"] == len(video()["video"][1])
    assert (storage / "sessions" / f"{data['session_id']}.json").exists()
    assert len(list((storage / "uploads").iterdir())) == 1
    assert "path" not in data


@pytest.mark.asyncio
async def test_missing_bowler_name(storage):
    data = fields()
    del data["bowler_name"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/sessions", data=data, files=video())
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_missing_video(storage):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/sessions", data=fields())
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unsupported_file_type(storage):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/sessions", data=fields(), files=video("practice.avi"))
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_file_exceeding_configured_limit_is_removed(storage):
    too_large = b"\x00\x00\x00\x18ftypisom" + b"x" * 40
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/sessions", data=fields(), files=video(content=too_large))
    assert response.status_code == 413
    assert list((storage / "uploads").iterdir()) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [("bowling_type", "unknown"), ("bowling_arm", "ambidextrous"), ("camera_view", "overhead")])
async def test_invalid_session_enum(storage, field, value):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/sessions", data=fields(**{field: value}), files=video())
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_session_ids_are_unique(storage):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/sessions", data=fields(), files=video())
        second = await client.post("/api/sessions", data=fields(), files=video())
    assert first.json()["session_id"] != second.json()["session_id"]


@pytest.mark.asyncio
async def test_saved_sessions_can_be_listed_without_filesystem_paths(storage):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/sessions", data=fields(), files=video())
        listed = await client.get("/api/sessions")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["session_id"] == created.json()["session_id"]
    assert "path" not in listed.json()[0]
