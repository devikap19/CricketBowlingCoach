"""Conservative, camera-aware landmark checks for 2D MoveNet predictions."""

from math import hypot, isfinite
from statistics import median

from app.pose.pose_constants import KEYPOINT_NAMES
from app.pose.pose_models import Keypoint

TORSO = (5, 6, 11, 12)
FACE = (0, 1, 2, 3, 4)
LIMB_SEGMENTS = ((5, 7), (7, 9), (6, 8), (8, 10), (11, 13), (13, 15), (12, 14), (14, 16))
LEFT_RIGHT_PAIRS = ((5, 6), (11, 12), (7, 8), (9, 10), (13, 14), (15, 16))


def _raw_number(value: float) -> float | str:
    if isfinite(value):
        return value
    if value != value:
        return "NaN"
    return "Infinity" if value > 0 else "-Infinity"


def _distance(a: Keypoint, b: Keypoint) -> float:
    return hypot(a.x - b.x, a.y - b.y)


def validate_keypoints(
    raw_points: list[dict],
    threshold: float,
    timestamp: float | None,
    previous: dict[int, tuple[float, float, float]] | None = None,
    camera_view: str = "other",
) -> tuple[list[Keypoint], bool | None, list[str], dict[int, tuple[float, float, float]]]:
    """Validate only relationships supported by the visible 2D evidence.

    Coordinates are never corrected. Projection overlap and incomplete context
    are represented as insufficient evidence rather than anatomical failure.
    """
    points: list[Keypoint] = []
    frame_warnings: list[str] = []
    normalized_raw = list(raw_points[:len(KEYPOINT_NAMES)])
    if len(normalized_raw) < len(KEYPOINT_NAMES):
        frame_warnings.append("incomplete_keypoint_sequence")
        normalized_raw.extend(
            {"name": KEYPOINT_NAMES[index], "x": float("nan"), "y": float("nan"), "confidence": float("nan")}
            for index in range(len(normalized_raw), len(KEYPOINT_NAMES))
        )
    for index, raw in enumerate(normalized_raw):
        x, y, confidence = float(raw["x"]), float(raw["y"]), float(raw["confidence"])
        coord_ok = isfinite(x) and isfinite(y) and 0 <= x <= 1 and 0 <= y <= 1
        conf_ok = isfinite(confidence) and 0 <= confidence <= 1
        meets = conf_ok and confidence >= threshold
        warnings = []
        if not isfinite(x) or not isfinite(y):
            warnings.append("non_finite_coordinate")
        elif not coord_ok:
            warnings.append("out_of_frame")
        if not conf_ok:
            warnings.append("invalid_confidence")
        elif not meets:
            warnings.append("low_confidence")
        points.append(Keypoint(
            name=raw.get("name", KEYPOINT_NAMES[index]), x=x if isfinite(x) else None, y=y if isfinite(y) else None,
            confidence=confidence if isfinite(confidence) else None, meets_threshold=meets,
            raw_x=_raw_number(x), raw_y=_raw_number(y), raw_confidence=_raw_number(confidence),
            coordinate_valid=coord_ok, confidence_valid=conf_ok,
            anatomical_valid=None, temporal_valid=None, validated_visible=False,
            validation_state="insufficient_evidence", validation_warnings=warnings,
        ))

    def usable(index: int) -> bool:
        return points[index].coordinate_valid and points[index].meets_threshold

    # Start with independent landmark evidence. Contextual checks below may
    # downgrade a point, but a missing torso joint does not invalidate others.
    for index, point in enumerate(points):
        if usable(index):
            point.anatomical_valid = True

    torso_complete = all(usable(index) for index in TORSO)
    torso_center = None
    torso_scale = None
    if torso_complete:
        shoulder_center = ((points[5].x + points[6].x) / 2, (points[5].y + points[6].y) / 2)
        hip_center = ((points[11].x + points[12].x) / 2, (points[11].y + points[12].y) / 2)
        torso_scale = hypot(shoulder_center[0] - hip_center[0], shoulder_center[1] - hip_center[1])
        torso_center = shoulder_center
        if torso_scale < .015:
            # A compressed or foreshortened torso cannot provide a useful body
            # scale; this is not proof that its landmarks are wrong.
            torso_complete = False
            torso_scale = None
            frame_warnings.append("torso_scale_insufficient_for_geometry")
    else:
        frame_warnings.append("insufficient_confident_torso_landmarks_for_geometry_validation")
        for index in TORSO:
            if usable(index):
                points[index].anatomical_valid = None
                points[index].validation_warnings.append("torso_context_unavailable")

    # Broad segment-length bounds catch grossly displaced predictions while
    # allowing projected proportions, flexion and arm positions to vary.
    for proximal, distal in LIMB_SEGMENTS:
        if usable(proximal) and usable(distal):
            length = _distance(points[proximal], points[distal])
            max_length = max(.45, (torso_scale or 0.0) * 3.5)
            if length > max_length:
                points[distal].anatomical_valid = False
                points[distal].validation_warnings.append("implausible_limb_segment_length")
                frame_warnings.append("implausible_limb_segment_length")

    # Use body-relative distances instead of image-up/image-down assumptions.
    # A bent, tilted or rotated trunk therefore does not fail a vertical-order test.
    if usable(0):
        if torso_center is not None and torso_scale is not None:
            if hypot(points[0].x - torso_center[0], points[0].y - torso_center[1]) > max(.45, torso_scale * 2.5):
                points[0].anatomical_valid = False
                points[0].validation_warnings.append("head_too_far_from_shoulder_center")
                frame_warnings.append("head_too_far_from_shoulder_center")
        face = [index for index in FACE if usable(index)]
        if len(face) >= 2:
            max_face_span = max(.25, (torso_scale or 0.0) * 1.75)
            for index in face:
                if index != 0 and usable(0) and _distance(points[0], points[index]) > max_face_span:
                    points[index].anatomical_valid = False
                    points[index].validation_warnings.append("inconsistent_head_landmark_cluster")
                    frame_warnings.append("inconsistent_head_landmark_cluster")

    # Coincident left/right predictions are common in side views and under
    # occlusion. Flag that pair as ambiguous without failing unrelated joints.
    for left, right in LEFT_RIGHT_PAIRS:
        if usable(left) and usable(right) and _distance(points[left], points[right]) < .003:
            for index in (left, right):
                points[index].anatomical_valid = None
                points[index].validation_warnings.append("left_right_projection_overlap_ambiguous")
            frame_warnings.append("left_right_projection_overlap_ambiguous")

    camera_geometry_ambiguous = False
    if camera_view in ("front", "rear") and torso_complete:
        shoulder_width = _distance(points[5], points[6])
        hip_width = _distance(points[11], points[12])
        # Severe projection differences can come from trunk rotation. Record the
        # ambiguity rather than applying a universal width ratio as a failure.
        if min(shoulder_width, hip_width) > .01 and max(shoulder_width, hip_width) / min(shoulder_width, hip_width) > 6:
            frame_warnings.append("shoulder_hip_projection_differs_check_camera_rotation")
            camera_geometry_ambiguous = True
            for index in TORSO:
                points[index].anatomical_valid = None
                points[index].validation_warnings.append("shoulder_hip_projection_differs_check_camera_rotation")
    elif camera_view == "other":
        frame_warnings.append("camera_view_relationships_not_assessed")
        camera_geometry_ambiguous = True
        for index in TORSO:
            if usable(index):
                points[index].anatomical_valid = None
                points[index].validation_warnings.append("camera_view_relationships_not_assessed")

    # Temporal validation is based on motion relative to the robust median
    # translation of visible joints. A high-confidence fast limb can move faster
    # than the torso without being rejected; missing joints are simply skipped.
    prior_deltas: dict[int, tuple[float, float, float]] = {}
    if previous and timestamp is not None:
        for index, point in enumerate(points):
            prior = previous.get(index)
            if usable(index) and prior:
                px, py, prior_time = prior
                dt = timestamp - prior_time
                if dt > 0:
                    prior_deltas[index] = ((point.x - px) / dt, (point.y - py) / dt, dt)
        if prior_deltas:
            core = [prior_deltas[index] for index in TORSO if index in prior_deltas]
            motion = core if len(core) >= 2 else list(prior_deltas.values())
            global_vx = median(item[0] for item in motion)
            global_vy = median(item[1] for item in motion)
            for index, (vx, vy, _) in prior_deltas.items():
                point = points[index]
                local_speed = hypot(vx - global_vx, vy - global_vy)
                limb = index in (7, 8, 9, 10, 13, 14, 15, 16)
                limit = max(6.0, 30 * (torso_scale or .1)) if limb else max(2.5, 12 * (torso_scale or .1))
                if local_speed > limit:
                    point.temporal_valid = False
                    point.validation_warnings.append("implausible_temporal_jump")
                    frame_warnings.append("implausible_temporal_jump")
                else:
                    point.temporal_valid = True

            # A likely label swap is ambiguous in 2D, especially during body
            # rotation. Mark only the paired joints insufficient, never failed.
            for left, right in ((5, 6), (11, 12), (7, 8), (9, 10), (13, 14), (15, 16)):
                if left not in previous or right not in previous or not usable(left) or not usable(right):
                    continue
                lx, ly, _ = previous[left]
                rx, ry, _ = previous[right]
                direct = hypot(points[left].x-lx, points[left].y-ly) + hypot(points[right].x-rx, points[right].y-ry)
                swapped = hypot(points[left].x-rx, points[left].y-ry) + hypot(points[right].x-lx, points[right].y-ly)
                if swapped + max(.03, (torso_scale or .1) * .15) < direct:
                    for index in (left, right):
                        if points[index].temporal_valid is not False:
                            points[index].temporal_valid = None
                            points[index].validation_warnings.append("possible_left_right_swap_or_rotation")
                    frame_warnings.append("possible_left_right_swap_or_rotation")

            # A very large segment-projection change can reflect rotation,
            # foreshortening or an association swap. Keep it reviewable without
            # converting a plausible 2D projection change into a failure.
            for proximal, distal in LIMB_SEGMENTS:
                if proximal not in previous or distal not in previous or not usable(proximal) or not usable(distal):
                    continue
                old_length = hypot(previous[proximal][0]-previous[distal][0], previous[proximal][1]-previous[distal][1])
                new_length = _distance(points[proximal], points[distal])
                if old_length > .02 and min(new_length, old_length) > 1e-6 and abs(new_length-old_length) > .2 and max(new_length, old_length) / min(new_length, old_length) > 3:
                    if points[distal].temporal_valid is not False:
                        points[distal].temporal_valid = None
                        points[distal].validation_warnings.append("limb_projection_change_ambiguous")
                    frame_warnings.append("limb_projection_change_ambiguous")

    current_valid: dict[int, tuple[float, float, float]] = {}
    for index, point in enumerate(points):
        if not usable(index):
            point.validation_state = "missing_or_outside_frame" if not point.coordinate_valid else "low_confidence"
        elif point.temporal_valid is False:
            point.validation_state = "temporally_inconsistent"
        elif point.anatomical_valid is False:
            point.validation_state = "anatomically_implausible"
        elif point.anatomical_valid is None or any(
            warning in point.validation_warnings
            for warning in ("possible_left_right_swap_or_rotation", "limb_projection_change_ambiguous")
        ):
            point.validation_state = "insufficient_evidence"
        else:
            point.validation_state = "confident_and_valid"
            if timestamp is not None:
                current_valid[index] = (point.x, point.y, timestamp)
        point.validated_visible = point.validation_state == "confident_and_valid"

    invalid = any(
        point.validation_state in ("anatomically_implausible", "temporally_inconsistent")
        for point in points if point.meets_threshold and point.coordinate_valid
    )
    ambiguous_temporal = any(warning in frame_warnings for warning in ("possible_left_right_swap_or_rotation", "limb_projection_change_ambiguous"))
    plausible = False if invalid else None if not torso_complete or ambiguous_temporal or camera_geometry_ambiguous else True
    if not any(point.meets_threshold and point.coordinate_valid for point in points):
        frame_warnings.append("insufficient_confident_landmarks")
        plausible = None
    return points, plausible, list(dict.fromkeys(frame_warnings)), current_valid
