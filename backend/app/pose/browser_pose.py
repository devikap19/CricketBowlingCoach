
"""Data models for browser-generated MoveNet predictions."""

from pydantic import BaseModel, Field, field_validator

from app.pose.pose_constants import KEYPOINT_NAMES
from app.pose.pose_models import CropCoordinates


class BrowserKeypoint(BaseModel):
    """One raw MoveNet landmark prediction."""

    name: str
    x: float = Field(ge=0, le=1, allow_inf_nan=False)
    y: float = Field(ge=0, le=1, allow_inf_nan=False)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)


class BrowserFramePrediction(BaseModel):
    """Raw predictions for one sampled video frame."""

    frame_number: int = Field(ge=0)
    timestamp_seconds: float = Field(ge=0, allow_inf_nan=False)
    keypoints: list[BrowserKeypoint] = Field(
        min_length=17,
        max_length=17,
    )

    @field_validator("keypoints")
    @classmethod
    def validate_keypoint_order(cls, points):
        names = [point.name for point in points]

        if names != KEYPOINT_NAMES:
            raise ValueError(
                "Keypoints must follow the standard MoveNet order."
            )

        return points


class BrowserPoseSubmission(BaseModel):
    """Collection of browser-generated frame predictions."""

    frames: list[BrowserFramePrediction] = Field(min_length=1)

    @field_validator("frames")
    @classmethod
    def validate_unique_frames(cls, frames):
        frame_numbers = [frame.frame_number for frame in frames]

        if len(frame_numbers) != len(set(frame_numbers)):
            raise ValueError("Duplicate frame numbers are not allowed.")

        return frames


class BrowserPoseCrop(BaseModel):
    """A cropped video frame prepared for browser inference."""

    frame_number: int = Field(ge=0)
    timestamp_seconds: float = Field(ge=0, allow_inf_nan=False)
    image_url: str = Field(min_length=1)
    crop: CropCoordinates
