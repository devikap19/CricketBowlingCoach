"""Video sampling, pose coverage calculation, and skeleton preview generation."""

from datetime import datetime, timezone
from math import ceil
from pathlib import Path

import cv2
import numpy as np

from app.core.config import settings
from app.pose.pose_constants import INPUT_SIZE, KEYPOINT_NAMES, MODEL_NAME
from app.pose.pose_models import CropCoordinates, InsufficientFrame, Keypoint, KeypointCoverage, PoseAssessment, PoseCropDiagnostics, PoseFrame, RegionCoverage
from app.pose.pose_validation import validate_keypoints
from app.pose.tracking_models import TrackingAssessment

REGIONS = {
    "head": (0, 1, 2, 3, 4),
    "upper_body": (5, 6, 11, 12),
    "arms": (7, 8, 9, 10),
    "lower_body": (13, 14, 15, 16),
}
SKELETON_LINKS = (
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (0, 1), (0, 2), (1, 3), (2, 4),
)


class VideoSamplingError(RuntimeError):
    """Raised when a video cannot provide any decodable sampled frames."""


def sample_frame_numbers(frame_count: int, fps: float | None, interval_seconds: float, max_frames: int, fallback_stride: int) -> tuple[list[int], int]:
    """Return zero-based sampled frame numbers and the effective frame stride."""
    if frame_count <= 0:
        return [], max(1, fallback_stride)
    limit = max(1, max_frames)
    interval_stride = max(1, round(fps * interval_seconds)) if fps and fps > 0 else max(1, fallback_stride)
    stride = max(interval_stride, ceil(frame_count / limit))
    return list(range(0, frame_count, stride))[:limit], stride


def _is_person_detected(keypoints: list[Keypoint], threshold: float) -> bool:
    visible = {index for index, point in enumerate(keypoints) if point.meets_threshold}
    torso_visible = bool(visible.intersection({5, 6, 11, 12}))
    limb_visible = bool(visible.intersection({7, 8, 9, 10, 13, 14, 15, 16}))
    return len(visible) >= 4 and torso_visible and limb_visible


def _region_status(coverage: float, has_samples: bool) -> str:
    if not has_samples or coverage < settings.pose_min_region_frame_coverage:
        return "unavailable"
    if coverage >= settings.pose_reliable_region_frame_coverage:
        return "reliable"
    return "limited"


def _draw_pose(frame: np.ndarray, keypoints: list[Keypoint], threshold: float, frame_number: int, timestamp: float | None) -> np.ndarray:
    overlay = frame.copy()
    height, width = frame.shape[:2]
    for first, second in SKELETON_LINKS:
        left, right = keypoints[first], keypoints[second]
        if left.validated_visible and right.validated_visible:
            p1 = (round(left.x * width), round(left.y * height))
            p2 = (round(right.x * width), round(right.y * height))
            if all(0 <= x < width and 0 <= y < height for x, y in (p1, p2)):
                cv2.line(overlay, p1, p2, (80, 220, 120), 2, cv2.LINE_AA)
    for point in keypoints:
        if point.validated_visible:
            center = (round(point.x * width), round(point.y * height))
            if 0 <= center[0] < width and 0 <= center[1] < height:
                cv2.circle(overlay, center, 4, (30, 180, 255), -1, cv2.LINE_AA)
    stamp = f"Frame {frame_number} | {timestamp:.2f}s" if timestamp is not None else f"Frame {frame_number}"
    cv2.rectangle(overlay, (0, 0), (width, 30), (0, 0, 0), -1)
    cv2.putText(overlay, stamp, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return overlay


def _padded_crop(box, width: int, height: int) -> tuple[CropCoordinates, bool]:
    """Calculate the exact clipped 15% horizontal / 10% vertical inference crop."""
    requested = (
        int((box.x - box.width * .15) * width),
        int((box.y - box.height * .10) * height),
        int((box.x + box.width * 1.15) * width),
        int((box.y + box.height * 1.10) * height),
    )
    left, top, right, bottom = requested
    clipped = left < 0 or top < 0 or right > width or bottom > height
    return CropCoordinates(
        left=max(0, left), top=max(0, top),
        right=min(width, right), bottom=min(height, bottom),
    ), clipped
    
def _crop_rgb_frame(
    rgb: np.ndarray,
    box,
) -> tuple[np.ndarray, CropCoordinates, bool]:
    """Extract the padded bowler crop from an RGB video frame."""
    height, width = rgb.shape[:2]
    crop, clipped = _padded_crop(box, width, height)

    roi = rgb[crop.top:crop.bottom, crop.left:crop.right]

    return roi, crop, clipped

def _tracker_match_tolerance(track, fps: float) -> float:
    """Allow half a normal tracker sampling step plus half-frame rounding."""
    times = sorted(point.timestamp_seconds for point in track)
    spacings = [later-earlier for earlier, later in zip(times, times[1:]) if later > earlier]
    half_frame = .5 / fps
    cadence_allowance = float(np.median(spacings)) / 2 if spacings else 0.0
    return cadence_allowance + half_frame + 1e-6


def _write_jpeg(path: Path, frame: np.ndarray) -> None:
    success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not success:
        raise OSError("Could not encode a pose preview image.")
    path.write_bytes(encoded.tobytes())


def extract_pose_assessment(
    session_id: str,
    video_path: Path,
    output_dir: Path,
    base_url: str | None,
    tracking: TrackingAssessment,
    camera_view: str,
    browser_predictions: dict[int, list[dict]],
) -> PoseAssessment:
    """Validate browser-generated predictions and save original/overlay previews.

    Browser keypoint coordinates are normalized relative to each confirmed
    tracked-bowler crop. This backend performs no pose-model inference.
    """
    if tracking is None or tracking.confirmed_interval is None:
        raise ValueError("Browser pose assessment requires confirmed bowler tracking.")
    if browser_predictions is None:
        raise ValueError("Browser pose predictions are required.")
    output_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        raise VideoSamplingError("OpenCV could not open the video.")

    reported_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    reported_fps = float(capture.get(cv2.CAP_PROP_FPS))
    fps = reported_fps if np.isfinite(reported_fps) and reported_fps > 0 else None
    positions, stride = sample_frame_numbers(
        reported_count,
        fps,
        settings.pose_sampling_interval_seconds,
        settings.pose_max_sampled_frames,
        settings.pose_fallback_sample_frame_stride,
    )
    all_positions = positions[:]
    selected_interval = tracking.confirmed_interval if tracking else None
    if selected_interval:
        positions = [p for p in positions if selected_interval.start_seconds <= p / fps <= selected_interval.end_seconds] if fps else []
        if fps:
            for boundary in (selected_interval.start_seconds, selected_interval.end_seconds):
                nearest = int(round(boundary * fps))
                if nearest < reported_count and selected_interval.start_seconds <= nearest/fps <= selected_interval.end_seconds and nearest not in positions:
                    positions.append(nearest)
            positions.sort()
    sampling_note = "Frames are sampled at the configured interval, capped at the configured maximum."
    if not reported_count:
        sampling_note = "The container did not report a frame count; a bounded fallback sample was read from the start of the video."
        positions = []
        all_positions = []
    if fps is None:
        sampling_note += " FPS metadata is unavailable, so timestamps are omitted and fallback frame spacing is used."

    if reported_count:
        decoded_frames = []
        for frame_number in positions:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ok, frame = capture.read()
            if ok and frame is not None:
                decoded_frames.append((frame_number, frame))
    else:
        decoded_frames = []
        frame_number = 0
        sampled = 0
        while sampled < settings.pose_max_sampled_frames:
            ok, frame = capture.read()
            if not ok or frame is None:
                break
            if frame_number % stride == 0:
                decoded_frames.append((frame_number, frame))
                sampled += 1
            frame_number += 1
    capture.release()
    if not decoded_frames:
        if selected_interval:
            raise VideoSamplingError("No sampleable frames fall inside the confirmed active interval.")
        raise VideoSamplingError("No decodable frames were available for pose estimation.")
    if tracking and selected_interval:
        tracking.active_frame_count = len(decoded_frames)
        tracking.excluded_idle_frame_count = max(0, len(all_positions) - len(decoded_frames))

    threshold = settings.pose_confidence_threshold
    if tracking:
        tracking.valid_bowler_pose_frame_count = 0
    prefix = base_url or f"/api/sessions/{session_id}/pose-frames"
    frames: list[PoseFrame] = []
    insufficient: list[InsufficientFrame] = []
    keypoint_scores: list[list[float]] = [[] for _ in KEYPOINT_NAMES]
    previous_valid: dict[int, tuple[float, float, float]] = {}
    track_by_time = tracking.track if tracking else []

    for frame_number, original in decoded_frames:
        timestamp = round(frame_number / fps, 3) if fps is not None else None
        tracked_box = None
        tracking_ok = tracking is None
        skip_reason = "selected_bowler_tracking_lost_or_uncertain"
        matched_point = None
        tracker_delta = None
        tracker_tolerance = None
        tracker_rejection = None
        if tracking:
            if timestamp is None:
                tracker_rejection = "pose_frame_timestamp_unavailable"
                skip_reason = tracker_rejection
            else:
                matched_point = next((point for point in track_by_time if point.frame_number == frame_number), None)
                tracker_tolerance = .5 / fps + 1e-6 if fps else None
                if matched_point is None:
                    matched_point = min(track_by_time, key=lambda point: abs(point.timestamp_seconds-timestamp), default=None)
                    tracker_tolerance = _tracker_match_tolerance(track_by_time, fps) if fps else None
                tracker_delta = abs(matched_point.timestamp_seconds-timestamp) if matched_point else None
                if matched_point is None:
                    tracker_rejection = "no_tracker_update_available"
                elif tracker_tolerance is None or tracker_delta > tracker_tolerance:
                    tracker_rejection = "nearest_tracker_update_outside_time_tolerance"
                elif matched_point.status != "tracked":
                    tracker_rejection = f"tracker_update_status_{matched_point.status}"
                elif matched_point.box is None:
                    tracker_rejection = "accepted_tracker_update_has_no_box"
                else:
                    tracked_box = matched_point.box
                    tracking_ok = True
                if tracker_rejection:
                    skip_reason = tracker_rejection
        # The diagnostic records the exact point selected above; no earlier
        # accepted crop is retained when this update is rejected.
        crop_diagnostic = PoseCropDiagnostics(
            frame_number=frame_number,
            timestamp_seconds=timestamp,
            tracker_frame_number=matched_point.frame_number if matched_point else None,
            tracker_timestamp_seconds=matched_point.timestamp_seconds if matched_point else None,
            tracker_status=matched_point.status if matched_point else None,
            tracker_match_delta_seconds=round(tracker_delta, 6) if tracker_delta is not None else None,
            tracker_match_tolerance_seconds=round(tracker_tolerance, 6) if tracker_tolerance is not None else None,
            tracker_box=matched_point.box if matched_point else None,
            tracker_update_accepted=tracking_ok if tracking else None,
            tracker_rejection_reason=tracker_rejection,
            pose_detected=False,
            confident_landmark_count=0,
        )
        if tracking_ok:
            rgb = cv2.cvtColor(original, cv2.COLOR_BGR2RGB)
            if tracked_box:
                height, width = original.shape[:2]
                roi, crop, clipped = _crop_rgb_frame(rgb, tracked_box)
                left, top, right, bottom = crop.left, crop.top, crop.right, crop.bottom
                crop_diagnostic.crop = crop
                crop_diagnostic.crop_width = int(roi.shape[1])
                crop_diagnostic.crop_height = int(roi.shape[0])
                crop_diagnostic.crop_clipped_by_image_bounds = clipped
                if roi.shape[0] < 48 or roi.shape[1] < 24:
                    tracking_ok = False
                    skip_reason = "selected_bowler_region_too_small_or_cropped"
                    crop_diagnostic.crop_rejection_reason = skip_reason
                else:
                    raw_points = browser_predictions.get(frame_number)
                    if raw_points is None:
                        tracking_ok = False
                        skip_reason = "browser_prediction_missing_for_sampled_frame"
                        crop_diagnostic.crop_rejection_reason = skip_reason
                    else:
                        raw_points = [dict(item) for item in raw_points]
                        for item in raw_points:
                            item["x"] = (left + float(item["x"]) * (right-left)) / width
                            item["y"] = (top + float(item["y"]) * (bottom-top)) / height
                        crop_diagnostic.coordinates_mapped_to_original_frame = True
            else:
                tracking_ok = False
                skip_reason = tracker_rejection or "accepted_tracker_update_has_no_box"
                crop_diagnostic.crop_rejection_reason = skip_reason
        if tracking_ok:
            if not isinstance(raw_points, list) or len(raw_points) != 17:
                raise ValueError("Pose inference must return exactly 17 keypoints.")
            raw_values = []
            for expected_name, raw in zip(KEYPOINT_NAMES, raw_points, strict=True):
                if raw.get("name") != expected_name:
                    raise ValueError("Pose inference keypoints are not in the expected MoveNet order.")
                raw_values.append({"name": expected_name, "x": float(raw["x"]), "y": float(raw["y"]), "confidence": float(raw["confidence"])})
            points, plausible, warnings, current_valid = validate_keypoints(
                raw_values, threshold, timestamp, previous_valid, camera_view
            )
            # Keep the latest valid observation per joint across temporary
            # occlusions; validation uses elapsed time to account for the gap.
            previous_valid.update(current_valid)
            detected = _is_person_detected(points, threshold)
            if tracking:
                tracking.valid_bowler_pose_frame_count += int(detected)
        else:
            points = [Keypoint(name=name, x=None, y=None, confidence=None, meets_threshold=False,
                               coordinate_valid=False, confidence_valid=False, validated_visible=False,
                               validation_warnings=[skip_reason]) for name in KEYPOINT_NAMES]
            plausible = None
            warnings = [skip_reason]
            detected = False
        crop_diagnostic.pose_detected = detected
        crop_diagnostic.confident_landmark_count = sum(point.meets_threshold for point in points)
        if not tracking_ok:
            crop_diagnostic.crop_rejection_reason = crop_diagnostic.crop_rejection_reason or skip_reason
        if not detected:
            reason = "Selected bowler tracking was lost or uncertain, or its region was too small/cropped; the frame was not sent to pose inference." if not tracking_ok else "Too few confident landmarks across the torso and limbs to count as a pose detection."
            insufficient.append(InsufficientFrame(frame_number=frame_number, timestamp_seconds=timestamp, reason=reason))
        if not detected:
            validation_outcome = "insufficient_evidence"
        elif plausible is False:
            validation_outcome = "validation_failed"
        elif plausible is True and not any(point.validation_state in ("insufficient_evidence", "low_confidence", "missing_or_outside_frame") for point in points) and not any(
            warning in warnings for warning in ("camera_view_relationships_not_assessed", "shoulder_hip_projection_differs_check_camera_rotation")
        ):
            validation_outcome = "validated"
        elif any(point.validation_state == "confident_and_valid" for point in points):
            validation_outcome = "partially_validated"
        else:
            validation_outcome = "insufficient_evidence"
        legacy_validation_status = {
            "validated": "valid",
            "partially_validated": "limited",
            "validation_failed": "invalid",
            "insufficient_evidence": "unavailable",
        }[validation_outcome]
        for index, point in enumerate(points):
            keypoint_scores[index].append(point.confidence if point.confidence_valid else 0.0)

        base_name = f"frame_{frame_number:08d}"
        original_name = f"{base_name}_original.jpg"
        overlay_name = f"{base_name}_pose.jpg"
        overlay = _draw_pose(original, points, threshold, frame_number, timestamp)
        _write_jpeg(output_dir / original_name, original)
        _write_jpeg(output_dir / overlay_name, overlay)
        frames.append(PoseFrame(
            frame_number=frame_number,
            timestamp_seconds=timestamp,
            detected=detected,
            keypoints=points,
            original_image_url=f"{prefix}/{original_name}",
            overlay_image_url=f"{prefix}/{overlay_name}",
            pose_validated=validation_outcome == "validated",
            anatomically_plausible=plausible,
            validation_warnings=warnings,
            validation_outcome=validation_outcome,
            validation_status=legacy_validation_status,
            crop_diagnostics=crop_diagnostic,
        ))

    sample_count = len(frames)
    detected_count = sum(frame.detected for frame in frames)
    overall_coverage = detected_count / sample_count if sample_count else 0.0
    overall_status = _region_status(overall_coverage, sample_count > 0)
    valid_landmark_count = sum(point.validated_visible for frame in frames for point in frame.keypoints)
    valid_landmark_coverage = valid_landmark_count / (sample_count * len(KEYPOINT_NAMES)) if sample_count else 0.0
    fully_validated_frames = sum(frame.validation_outcome == "validated" for frame in frames)
    partial_frames = sum(frame.validation_outcome == "partially_validated" for frame in frames)
    failed_frames = sum(frame.validation_outcome == "validation_failed" for frame in frames)
    insufficient_frames = sum(frame.validation_outcome == "insufficient_evidence" for frame in frames)
    validation_evidence_frames = sum(frame.anatomically_plausible is not None for frame in frames)
    plausible_coverage = fully_validated_frames / sample_count if sample_count else 0.0
    if validation_evidence_frames == 0:
        validation_status = "unavailable"
    elif failed_frames:
        validation_status = "invalid"
    elif partial_frames or insufficient_frames:
        validation_status = "limited"
    else:
        validation_status = "valid"
    regions = []
    for name, indices in REGIONS.items():
        required = ceil(len(indices) / 2)
        visible_frames = sum(sum(frame.keypoints[index].meets_threshold for index in indices) >= required for frame in frames)
        validated_frames = sum(
            sum(frame.keypoints[index].validated_visible for index in indices) >= required
            and not any(frame.keypoints[index].validation_state in ("anatomically_implausible", "temporally_inconsistent") for index in indices)
            for frame in frames
        )
        sufficient_frames = sum(
            sum(frame.keypoints[index].meets_threshold and frame.keypoints[index].coordinate_valid for index in indices) >= required
            and sum(frame.keypoints[index].validation_state == "insufficient_evidence" for index in indices) < required
            for frame in frames
        )
        region_failed_frames = sum(any(frame.keypoints[index].validation_state in ("anatomically_implausible", "temporally_inconsistent") for index in indices) for frame in frames)
        region_insufficient_frames = sum(
            sum(frame.keypoints[index].meets_threshold and frame.keypoints[index].coordinate_valid for index in indices) < required
            or sum(frame.keypoints[index].validation_state == "insufficient_evidence" for index in indices) >= required
            for frame in frames
            if not any(frame.keypoints[index].validation_state in ("anatomically_implausible", "temporally_inconsistent") for index in indices)
        )
        coverage = visible_frames / sample_count if sample_count else 0.0
        validated_coverage = validated_frames / sample_count if sample_count else 0.0
        region_reasons: dict[str, int] = {}
        for frame in frames:
            for index in indices:
                for warning in frame.keypoints[index].validation_warnings:
                    region_reasons[warning] = region_reasons.get(warning, 0) + 1
        if not sample_count or (sufficient_frames == 0 and region_insufficient_frames == 0 and region_failed_frames == 0):
            region_validation_status = "unavailable"
        elif region_failed_frames:
            region_validation_status = "invalid"
        elif validated_frames == sufficient_frames and region_insufficient_frames == 0:
            region_validation_status = "valid"
        elif validated_frames or region_insufficient_frames:
            region_validation_status = "limited"
        else:
            region_validation_status = "unavailable"
        status = _region_status(validated_coverage, sample_count > 0)
        regions.append(RegionCoverage(
            name=name,
            visible_frames=visible_frames,
            sampled_frames=sample_count,
            frame_coverage_percent=round(coverage * 100, 2),
            status=status,
            explanation=(f"At least {required} of {len(indices)} keypoints were confident and in-frame in {visible_frames}/{sample_count} frames; "
                         f"{validated_frames}/{sample_count} frames had enough validated landmarks. Evidence: {sufficient_frames}, "
                         f"failed: {region_failed_frames}, insufficient: {region_insufficient_frames}."),
            validated_visible_frames=validated_frames,
            validated_frame_coverage_percent=round(validated_coverage * 100, 2),
            validation_status=region_validation_status,
            validation_warnings=sorted(region_reasons),
            sufficient_evidence_frames=sufficient_frames,
            failed_frames=region_failed_frames,
            insufficient_evidence_frames=region_insufficient_frames,
            validation_reason_counts=region_reasons,
        ))

    keypoint_coverage = []
    for name, scores in zip(KEYPOINT_NAMES, keypoint_scores, strict=True):
        visible_count = sum(score >= threshold for score in scores)
        keypoint_coverage.append(KeypointCoverage(
            name=name,
            mean_confidence=round(float(np.mean(scores)), 4),
            median_confidence=round(float(np.median(scores)), 4),
            detected_frames=visible_count,
            sampled_frames=sample_count,
            visible_frame_percent=round(visible_count / sample_count * 100, 2) if sample_count else 0.0,
            coordinate_valid_frames=sum(frame.keypoints[KEYPOINT_NAMES.index(name)].coordinate_valid for frame in frames),
            validated_visible_frames=sum(frame.keypoints[KEYPOINT_NAMES.index(name)].validated_visible for frame in frames),
            validated_visible_frame_percent=round(sum(frame.keypoints[KEYPOINT_NAMES.index(name)].validated_visible for frame in frames) / sample_count * 100, 2) if sample_count else 0.0,
            validation_warning_frames=sum(bool(frame.keypoints[KEYPOINT_NAMES.index(name)].validation_warnings) for frame in frames),
            validation_state_counts={
                state: sum(frame.keypoints[KEYPOINT_NAMES.index(name)].validation_state == state for frame in frames)
                for state in sorted({frame.keypoints[KEYPOINT_NAMES.index(name)].validation_state for frame in frames})
            },
        ))

    if detected_count == 0:
        summary = "MoveNet did not find enough confident landmarks to identify a pose in the sampled frames. This may reflect framing, occlusion, lighting, clothing, or model limitations; it is not a technique judgement."
    else:
        summary = (f"Pose detected in {detected_count}/{sample_count} sampled frames. Validation: {fully_validated_frames} validated, "
                  f"{partial_frames} partial, {insufficient_frames} insufficient evidence, {failed_frames} failed. "
                  "Review flagged frames; confidence and 2D checks do not establish biomechanics or bowling technique.")

    return PoseAssessment(
        session_id=session_id,
        assessed_at=datetime.now(timezone.utc),
        model=MODEL_NAME,
        model_input_size=INPUT_SIZE,
        confidence_threshold=threshold,
        sampling_interval_seconds=settings.pose_sampling_interval_seconds,
        sampling_note=sampling_note,
        sampled_frame_count=sample_count,
        validation_schema_version=2,
        detected_frame_count=detected_count,
        overall_frame_detection_coverage_percent=round(overall_coverage * 100, 2),
        overall_detection_status=overall_status,
        summary=summary,
        regions=regions,
        keypoint_coverage=keypoint_coverage,
        insufficient_detection_frames=insufficient,
        frames=frames,
        raw_pose_detection_coverage_percent=round(overall_coverage * 100, 2),
        valid_landmark_coverage_percent=round(valid_landmark_coverage * 100, 2),
        anatomically_plausible_pose_coverage_percent=round(plausible_coverage * 100, 2),
        pose_validation_status=validation_status,
        body_visibility_status=_region_status(valid_landmark_coverage, sample_count > 0),
        camera_view=camera_view,
        validation_evidence_frame_count=validation_evidence_frames,
        validation_failed_frame_count=failed_frames,
        insufficient_evidence_frame_count=insufficient_frames,
        manual_review_frame_numbers=[frame.frame_number for frame in frames if frame.validation_outcome != "validated"],
        subject_identity_explanation="MoveNet returns a single-person pose prediction. This workflow does not track or verify subject identity." if not tracking else "The coach selected the person. OpenCV MIL updates the box with an HSV appearance check; optical-flow features estimate crop scale only. Identity is not independently verified.",
        subject_identity_status="not_assessed" if not tracking else "coach_selected",
        tracking=tracking,
    )

