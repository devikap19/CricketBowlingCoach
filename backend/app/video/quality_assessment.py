"""OpenCV-based, heuristic quality checks for uploaded bowling videos."""

from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from app.core.config import settings
from app.video.quality_models import QualityAssessment, QualityMetric, VideoMetadata

SAMPLE_LIMIT = 12
MIN_CAMERA_TRACKS = 8


def _metric(name, value, status, explanation, recommendation=None):
    return QualityMetric(name=name, value=value, status=status, explanation=explanation, recommendation=recommendation)


def assess_video(session_id: str, video_path: Path, camera_view: str) -> QualityAssessment:
    """Inspect metadata and evenly sampled frames without retaining the video in memory."""
    file_size = video_path.stat().st_size
    capture = cv2.VideoCapture(str(video_path))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or None
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or None
    reported_fps = float(capture.get(cv2.CAP_PROP_FPS))
    fps = reported_fps if np.isfinite(reported_fps) and reported_fps > 0 else None
    reported_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_count = reported_frames if reported_frames > 0 else None
    duration = frame_count / fps if frame_count and fps else None

    opened = capture.isOpened()
    gray_frames = []
    color_frames = []
    if opened:
        if frame_count:
            positions = np.unique(np.linspace(0, max(frame_count - 1, 0), min(SAMPLE_LIMIT, frame_count), dtype=int))
            for position in positions:
                capture.set(cv2.CAP_PROP_POS_FRAMES, int(position))
                ok, frame = capture.read()
                if ok and frame is not None:
                    color_frames.append(frame)
                    gray_frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        else:
            # Some containers omit frame count. Read a bounded sample from the start.
            for _ in range(SAMPLE_LIMIT):
                ok, frame = capture.read()
                if not ok or frame is None:
                    break
                color_frames.append(frame)
                gray_frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    capture.release()

    sample_count = len(gray_frames)
    enough_samples = sample_count >= settings.quality_min_decodable_samples
    metadata = VideoMetadata(
        width=width,
        height=height,
        fps=fps,
        total_frames=frame_count,
        duration_seconds=round(duration, 3) if duration is not None else None,
        file_size_bytes=file_size,
    )

    metrics = []
    integrity_ok = opened and sample_count > 0
    integrity_status = "reliable" if integrity_ok else "unavailable"
    metrics.append(_metric(
        "Video integrity",
        {"opened": opened, "decodable_sample_frames": sample_count},
        integrity_status,
        "OpenCV opened the file and decoded sampled frames." if integrity_ok else "OpenCV could not open or decode a frame from this file.",
        None if integrity_ok else "Re-export the recording as a standard MP4 or MOV and upload it again.",
    ))

    metrics.append(_metric(
        "Video metadata",
        metadata.model_dump(),
        "reliable" if width and height else "unavailable",
        "Dimensions, frame rate, frame count, duration, and file size are reported when the container provides valid values. Zero or invalid FPS/frame counts are left unavailable.",
        "Use a playable video with valid frame dimensions and timing metadata." if not width or not height else None,
    ))

    if width and height:
        short_side, long_side = sorted((width, height))
        adequate = short_side >= settings.quality_min_height and long_side >= settings.quality_min_width
        metrics.append(_metric(
            "Resolution",
            {"width": width, "height": height, "minimum_short_side": settings.quality_min_height, "minimum_long_side": settings.quality_min_width, "classification": "meets_initial_minimum" if adequate else "below_initial_minimum"},
            "reliable",
            "Resolution is read from the video stream. Meeting this minimum does not guarantee that the bowler or joints are visible enough for pose estimation.",
            None if adequate else f"Record at least {settings.quality_min_width} x {settings.quality_min_height} pixels (orientation independent).",
        ))
    else:
        metrics.append(_metric("Resolution", None, "unavailable", "The video dimensions could not be read."))

    if fps is not None:
        metrics.append(_metric(
            "Frame rate",
            {"fps": round(fps, 3), "minimum_fps": settings.quality_min_fps, "classification": "meets_initial_minimum" if fps >= settings.quality_min_fps else "below_initial_minimum"},
            "reliable",
            "Frame rate is read from container metadata. A nominal FPS does not reveal variable-frame-rate timing or guarantee sharp motion frames.",
            None if fps >= settings.quality_min_fps else f"Prefer a recording at {settings.quality_min_fps:g} FPS or higher to inspect fast movement.",
        ))
    else:
        metrics.append(_metric("Frame rate", None, "unavailable", "The video reports an invalid or zero frame rate."))

    if enough_samples:
        brightness = np.concatenate([frame.reshape(-1) for frame in gray_frames]).astype(np.float32)
        mean_brightness = float(np.mean(brightness))
        dark_fraction = float(np.mean(brightness <= settings.quality_dark_pixel_threshold))
        bright_fraction = float(np.mean(brightness >= settings.quality_bright_pixel_threshold))
        lighting_issue = dark_fraction >= settings.quality_max_extreme_pixel_fraction or bright_fraction >= settings.quality_max_extreme_pixel_fraction
        lighting_parts = []
        if dark_fraction >= settings.quality_max_extreme_pixel_fraction:
            lighting_parts.append("many sampled pixels are very dark")
        if bright_fraction >= settings.quality_max_extreme_pixel_fraction:
            lighting_parts.append("many sampled pixels are very bright")
        metrics.append(_metric(
            "Brightness and lighting",
            {"sample_count": sample_count, "mean_brightness_0_255": round(mean_brightness, 2), "very_dark_pixel_percent": round(dark_fraction * 100, 2), "very_bright_pixel_percent": round(bright_fraction * 100, 2), "dark_pixel_threshold": settings.quality_dark_pixel_threshold, "bright_pixel_threshold": settings.quality_bright_pixel_threshold},
            "reliable" if sample_count >= 6 else "limited",
            ("Sampled frames suggest uneven or extreme lighting: " + "; ".join(lighting_parts) + ".") if lighting_issue else "Brightness and extreme-pixel proportions were measured across sampled frames; these image-wide values may not describe lighting on the bowler.",
            "Improve lighting or avoid pointing the camera toward a bright light source." if lighting_issue else None,
        ))

        blur_scores = [float(cv2.Laplacian(frame, cv2.CV_64F).var()) for frame in gray_frames]
        lowest_blur = min(blur_scores)
        average_blur = float(np.mean(blur_scores))
        blur_issue = lowest_blur < settings.quality_min_blur_variance
        metrics.append(_metric(
            "Motion blur",
            {"sample_count": sample_count, "average_laplacian_variance": round(average_blur, 2), "lowest_laplacian_variance": round(lowest_blur, 2), "heuristic_minimum": settings.quality_min_blur_variance},
            "reliable" if sample_count >= 6 else "limited",
            "Variance of the Laplacian estimates frame sharpness. This heuristic depends on scene texture and cannot reliably separate motion blur from focus or naturally smooth backgrounds.",
            "Use a faster shutter or steadier lighting and re-record if sampled frames appear soft." if blur_issue else None,
        ))
    else:
        metrics.append(_metric("Brightness and lighting", None, "unavailable", f"Only {sample_count} frame(s) could be sampled; at least {settings.quality_min_decodable_samples} are needed."))
        metrics.append(_metric("Motion blur", None, "unavailable", f"Only {sample_count} frame(s) could be sampled; at least {settings.quality_min_decodable_samples} are needed."))

    camera_shifts = []
    camera_inlier_ratios = []
    if enough_samples:
        for previous, current in zip(gray_frames, gray_frames[1:]):
            points = cv2.goodFeaturesToTrack(previous, maxCorners=250, qualityLevel=0.01, minDistance=8, blockSize=7)
            if points is None or len(points) < MIN_CAMERA_TRACKS:
                continue
            tracked, status, _ = cv2.calcOpticalFlowPyrLK(previous, current, points, None)
            if tracked is None or status is None:
                continue
            source = points[status.reshape(-1) == 1]
            target = tracked[status.reshape(-1) == 1]
            if len(source) < MIN_CAMERA_TRACKS:
                continue
            transform, inliers = cv2.estimateAffinePartial2D(source, target, method=cv2.RANSAC, ransacReprojThreshold=3.0)
            if transform is not None and inliers is not None:
                camera_shifts.append(float(np.hypot(transform[0, 2], transform[1, 2])))
                camera_inlier_ratios.append(float(np.mean(inliers)))
    if camera_shifts:
        median_shift = float(np.median(camera_shifts))
        metrics.append(_metric(
            "Camera stability",
            {"tracked_frame_pairs": len(camera_shifts), "median_global_shift_pixels_per_sampled_pair": round(median_shift, 2), "median_ransac_inlier_fraction": round(float(np.median(camera_inlier_ratios)), 3)},
            "limited",
            "Feature tracking estimates global frame motion. Subject movement, zoom, panning, and scene texture can affect the estimate, so this cannot confidently identify camera movement on its own.",
            "Review the recording for camera shake; use a fixed support if the view visibly moves." if median_shift > 5 else None,
        ))
    else:
        metrics.append(_metric("Camera stability", None, "unavailable", "Too few stable visual features could be tracked across sampled frames to estimate global frame motion."))

    metrics.append(_metric("Bowler visibility", None, "unavailable", "Full-body and joint visibility are not assessed in this stage."))
    metrics.append(_metric("Pose coverage", None, "unavailable", "Pose estimation is not implemented in this stage."))

    resolution_ok = bool(width and height and min(width, height) >= settings.quality_min_height and max(width, height) >= settings.quality_min_width)
    fps_ok = fps is not None and fps >= settings.quality_min_fps
    lighting_bad = any(metric.name == "Brightness and lighting" and metric.recommendation for metric in metrics)
    blur_bad = any(metric.name == "Motion blur" and metric.recommendation for metric in metrics)
    if not integrity_ok or not enough_samples or not resolution_ok or not fps_ok or lighting_bad or blur_bad:
        overall = "not_suitable"
        summary = "The video has an integrity, sampling, resolution, frame-rate, lighting, or sharpness issue that should be reviewed before analysis."
    elif any(metric.status != "reliable" for metric in metrics if metric.name not in {"Camera stability", "Bowler visibility", "Pose coverage"}) or any(metric.status == "limited" for metric in metrics if metric.name not in {"Camera stability", "Bowler visibility", "Pose coverage"}):
        overall = "suitable_with_limitations"
        summary = "The video meets the initial technical minimums, with one or more measurements limited or unavailable. Coach review is still required."
    else:
        overall = "suitable"
        summary = "The video meets the initial technical minimums for proceeding to a future analysis stage. This is not a pose-visibility or technique assessment."

    return QualityAssessment(
        session_id=session_id,
        assessed_at=datetime.now(timezone.utc),
        overall_assessment=overall,
        summary=summary,
        metadata=metadata,
        camera_view=camera_view,
        metrics=metrics,
    )
