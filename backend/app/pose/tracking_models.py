"""Coach selection, subject tracking, and active interval response models."""

from typing import Literal

from pydantic import BaseModel, Field


class Box(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class SubjectSelection(BaseModel):
    timestamp_seconds: float = Field(ge=0)
    box: Box


class TrackPoint(BaseModel):
    frame_number: int
    timestamp_seconds: float
    box: Box | None = None
    status: Literal["tracked", "uncertain", "lost", "outside_frame"]
    feature_count: int
    appearance_distance: float | None = None
    appearance_distance_change: float | None = None
    center_movement_from_previous: float | None = None
    width_scale_from_previous: float | None = None
    height_scale_from_previous: float | None = None


class TrackInterruption(BaseModel):
    start_seconds: float
    end_seconds: float
    reason: str


class ActiveInterval(BaseModel):
    start_seconds: float
    end_seconds: float
    confidence: Literal["high", "medium", "low"]
    reason: str


class TrackingAssessment(BaseModel):
    session_id: str
    selection_status: Literal["coach_selected"] = "coach_selected"
    selected_at_seconds: float
    selected_box: Box
    tracker_method: str
    scale_estimation_method: str | None = None
    feature_count_semantics: str = "A value of 0 means no persistent point tracks are maintained for subject identity."
    appearance_distance_metric: str = "Bhattacharyya distance between HSV histograms; lower means more similar appearance, not higher identity confidence."
    appearance_signature: list[float]
    duration_seconds: float
    sampled_track_count: int
    tracked_sample_count: int
    tracking_coverage_percent: float
    tracker_update_coverage_percent: float | None = None
    identity_validation_status: Literal["not_independently_verified"] = "not_independently_verified"
    identity_validation_explanation: str = "No independent person detector or identity verifier validates MIL updates."
    tracking_interruptions: list[TrackInterruption]
    track: list[TrackPoint]
    proposed_intervals: list[ActiveInterval]
    interval_detection_status: Literal["proposed", "uncertain", "unavailable"]
    confirmed_interval: ActiveInterval | None = None
    interval_source: Literal["automatic", "manual", "not_confirmed"] = "not_confirmed"
    active_frame_count: int = 0
    excluded_idle_frame_count: int = 0
    valid_bowler_pose_frame_count: int = 0

