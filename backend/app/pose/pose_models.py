"""Structured response models for raw and validated pose results."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.video.quality_models import MetricStatus
from app.pose.tracking_models import Box, TrackingAssessment

ValidationStatus = Literal["valid", "invalid", "limited", "unavailable"]
LandmarkValidationState = Literal[
    "confident_and_valid", "low_confidence", "missing_or_outside_frame",
    "anatomically_implausible", "temporally_inconsistent", "insufficient_evidence",
]
FrameValidationOutcome = Literal[
    "validated", "partially_validated", "insufficient_evidence", "validation_failed", "not_assessed",
]


class Keypoint(BaseModel):
    name: str
    x: float | None
    y: float | None
    confidence: float | None
    meets_threshold: bool
    raw_x: float | str | None = None
    raw_y: float | str | None = None
    raw_confidence: float | str | None = None
    coordinate_valid: bool = False
    confidence_valid: bool = False
    anatomical_valid: bool | None = None
    temporal_valid: bool | None = None
    validated_visible: bool = False
    validation_state: LandmarkValidationState = "insufficient_evidence"
    validation_warnings: list[str] = Field(default_factory=list)


class CropCoordinates(BaseModel):
    left: int
    top: int
    right: int
    bottom: int


class PoseCropDiagnostics(BaseModel):
    frame_number: int
    timestamp_seconds: float | None
    tracker_frame_number: int | None = None
    tracker_timestamp_seconds: float | None = None
    tracker_status: Literal["tracked", "uncertain", "lost", "outside_frame"] | None = None
    tracker_match_delta_seconds: float | None = None
    tracker_match_tolerance_seconds: float | None = None
    tracker_box: Box | None = None
    tracker_update_accepted: bool | None = None
    tracker_rejection_reason: str | None = None
    crop: CropCoordinates | None = None
    crop_width: int | None = None
    crop_height: int | None = None
    crop_clipped_by_image_bounds: bool | None = None
    crop_rejection_reason: str | None = None
    pose_detected: bool
    confident_landmark_count: int
    coordinates_mapped_to_original_frame: bool | None = None


class PoseFrame(BaseModel):
    frame_number: int
    timestamp_seconds: float | None
    detected: bool
    keypoints: list[Keypoint]
    original_image_url: str
    overlay_image_url: str
    pose_validated: bool = False
    anatomically_plausible: bool | None = None
    validation_status: ValidationStatus = "unavailable"
    validation_outcome: FrameValidationOutcome = "not_assessed"
    validation_warnings: list[str] = Field(default_factory=list)
    crop_diagnostics: PoseCropDiagnostics | None = None


class KeypointCoverage(BaseModel):
    name: str
    mean_confidence: float
    median_confidence: float
    detected_frames: int
    sampled_frames: int
    visible_frame_percent: float
    coordinate_valid_frames: int = 0
    validated_visible_frames: int = 0
    validated_visible_frame_percent: float = 0.0
    validation_warning_frames: int = 0
    validation_state_counts: dict[str, int] = Field(default_factory=dict)


class RegionCoverage(BaseModel):
    name: Literal["head", "upper_body", "arms", "lower_body"]
    visible_frames: int
    sampled_frames: int
    frame_coverage_percent: float
    status: MetricStatus
    explanation: str
    validated_visible_frames: int = 0
    validated_frame_coverage_percent: float = 0.0
    validation_status: ValidationStatus = "unavailable"
    validation_warnings: list[str] = Field(default_factory=list)
    sufficient_evidence_frames: int = 0
    failed_frames: int = 0
    insufficient_evidence_frames: int = 0
    validation_reason_counts: dict[str, int] = Field(default_factory=dict)


class InsufficientFrame(BaseModel):
    frame_number: int
    timestamp_seconds: float | None
    reason: str


class PoseAssessment(BaseModel):
    session_id: str
    assessed_at: datetime
    model: str
    model_input_size: int
    confidence_threshold: float
    sampling_interval_seconds: float
    sampling_note: str
    sampled_frame_count: int
    detected_frame_count: int
    overall_frame_detection_coverage_percent: float
    overall_detection_status: MetricStatus
    summary: str
    regions: list[RegionCoverage]
    keypoint_coverage: list[KeypointCoverage]
    insufficient_detection_frames: list[InsufficientFrame]
    frames: list[PoseFrame]
    validation_schema_version: int = 1
    raw_pose_detection_coverage_percent: float = 0.0
    valid_landmark_coverage_percent: float = 0.0
    anatomically_plausible_pose_coverage_percent: float = 0.0
    pose_validation_status: ValidationStatus = "unavailable"
    body_visibility_status: MetricStatus = "unavailable"
    camera_view: Literal["front", "side", "rear", "other"] = "other"
    validation_evidence_frame_count: int = 0
    validation_failed_frame_count: int = 0
    insufficient_evidence_frame_count: int = 0
    manual_review_frame_numbers: list[int] = Field(default_factory=list)
    subject_identity_status: Literal["not_assessed", "coach_selected"] = "not_assessed"
    subject_identity_explanation: str = "Subject identity is not assessed in this stage."
    tracking: TrackingAssessment | None = None
    biomechanics: dict = Field(default_factory=dict)
