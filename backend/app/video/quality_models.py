"""Response models for evidence-based video quality assessment."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

MetricStatus = Literal["reliable", "limited", "unavailable"]
OverallStatus = Literal["suitable", "suitable_with_limitations", "not_suitable"]


class QualityMetric(BaseModel):
    name: str
    value: Any | None
    status: MetricStatus
    explanation: str
    recommendation: str | None = None


class VideoMetadata(BaseModel):
    width: int | None
    height: int | None
    fps: float | None
    total_frames: int | None
    duration_seconds: float | None
    file_size_bytes: int


class QualityAssessment(BaseModel):
    session_id: str
    assessed_at: datetime
    overall_assessment: OverallStatus
    summary: str
    metadata: VideoMetadata
    camera_view: str
    metrics: list[QualityMetric]
