"""Prepare tracked bowler crops for browser-side MoveNet inference."""

from __future__ import annotations

from math import ceil
from pathlib import Path

import cv2
import numpy as np

from app.core.config import settings
from app.pose.browser_pose import BrowserPoseCrop
from app.pose.pose_models import CropCoordinates
from app.pose.tracking_models import TrackingAssessment


class BrowserPosePreparationError(RuntimeError):
    """Raised when tracked frames cannot be prepared for browser inference."""


def _sample_frame_numbers(frame_count: int, fps: float) -> list[int]:
    """Match the bounded sampling policy used by pose extraction."""
    if frame_count <= 0:
        return []
    limit = max(1, settings.pose_max_sampled_frames)
    interval_stride = max(1, round(fps * settings.pose_sampling_interval_seconds))
    stride = max(interval_stride, ceil(frame_count / limit))
    return list(range(0, frame_count, stride))[:limit]


def _padded_crop(box, width: int, height: int) -> CropCoordinates:
    """Return the clipped crop with the same padding as pose extraction."""
    requested = (
        int((box.x - box.width * 0.15) * width),
        int((box.y - box.height * 0.10) * height),
        int((box.x + box.width * 1.15) * width),
        int((box.y + box.height * 1.10) * height),
    )
    left, top, right, bottom = requested
    return CropCoordinates(
        left=max(0, left),
        top=max(0, top),
        right=min(width, right),
        bottom=min(height, bottom),
    )


def _tracker_match_tolerance(track, fps: float) -> float:
    """Allow half a tracker sampling step plus half-frame rounding."""
    times = sorted(point.timestamp_seconds for point in track)
    spacings = [
        later - earlier
        for earlier, later in zip(times, times[1:])
        if later > earlier
    ]
    cadence_allowance = float(np.median(spacings)) / 2 if spacings else 0.0
    return cadence_allowance + 0.5 / fps + 1e-6


def _match_tracker_point(tracking: TrackingAssessment, frame_number: int, timestamp: float, fps: float):
    """Find the tracker update valid for this video frame."""
    track = tracking.track
    matched = next((point for point in track if point.frame_number == frame_number), None)
    tolerance = 0.5 / fps + 1e-6

    if matched is None:
        matched = min(
            track,
            key=lambda point: abs(point.timestamp_seconds - timestamp),
            default=None,
        )
        tolerance = _tracker_match_tolerance(track, fps)

    if matched is None:
        return None

    delta = abs(matched.timestamp_seconds - timestamp)
    if delta > tolerance or matched.status != "tracked" or matched.box is None:
        return None
    return matched


def prepare_browser_pose_crops(
    session_id: str,
    video_path: Path,
    output_dir: Path,
    tracking: TrackingAssessment,
    base_url: str | None = None,
) -> list[BrowserPoseCrop]:
    """Write sampled tracked bowler crops and return browser-facing URLs.

    Only frames inside the coach-confirmed interval with a valid tracked box
    are returned. Crop coordinates use original-video pixel coordinates.
    """
    if tracking.confirmed_interval is None:
        raise BrowserPosePreparationError(
            "Confirm the bowler's active delivery interval before pose inference."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        raise BrowserPosePreparationError("OpenCV could not open the session video.")

    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps_value = float(capture.get(cv2.CAP_PROP_FPS))
        if not np.isfinite(fps_value) or fps_value <= 0:
            raise BrowserPosePreparationError(
                "Video FPS metadata is unavailable; tracked crops cannot be timestamped safely."
            )
        if frame_count <= 0:
            raise BrowserPosePreparationError(
                "The video frame count is unavailable; browser crop preparation cannot sample the confirmed interval."
            )

        fps = fps_value
        positions = _sample_frame_numbers(frame_count, fps)
        interval = tracking.confirmed_interval
        positions = [
            number for number in positions
            if interval.start_seconds <= number / fps <= interval.end_seconds
        ]

        for boundary in (interval.start_seconds, interval.end_seconds):
            nearest = int(round(boundary * fps))
            if (
                nearest < frame_count
                and interval.start_seconds <= nearest / fps <= interval.end_seconds
                and nearest not in positions
            ):
                positions.append(nearest)
        positions.sort()

        if not positions:
            raise BrowserPosePreparationError(
                "No sampled video frames fall inside the confirmed delivery interval."
            )

        prefix = base_url or f"/api/sessions/{session_id}/browser-pose-crops"
        results: list[BrowserPoseCrop] = []

        for frame_number in positions:
            timestamp = round(frame_number / fps, 3)
            matched = _match_tracker_point(tracking, frame_number, timestamp, fps)
            if matched is None:
                continue

            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue

            height, width = frame.shape[:2]
            crop = _padded_crop(matched.box, width, height)
            if crop.right <= crop.left or crop.bottom <= crop.top:
                continue

            roi = frame[crop.top:crop.bottom, crop.left:crop.right]
            if roi.shape[0] < 48 or roi.shape[1] < 24:
                continue

            filename = f"frame_{frame_number:08d}.jpg"
            success, encoded = cv2.imencode(
                ".jpg", roi, [cv2.IMWRITE_JPEG_QUALITY, 92]
            )
            if not success:
                continue

            (output_dir / filename).write_bytes(encoded.tobytes())
            results.append(
                BrowserPoseCrop(
                    frame_number=frame_number,
                    timestamp_seconds=timestamp,
                    image_url=f"{prefix}/{filename}",
                    crop=crop,
                )
            )

        if not results:
            raise BrowserPosePreparationError(
                "No usable tracked bowler crops were available inside the confirmed interval."
            )
        return results
    finally:
        capture.release()
