"""Confidence-aware 2D measurements for an end-on (batsman's-end) camera.

These are image-plane measurements, not 3D anatomical joint mechanics.
"""
from __future__ import annotations
from math import atan2, degrees, hypot, isfinite
from statistics import median

MIN_CONFIDENCE = 0.35


def _point(frame, name):
    kp = next((p for p in frame.keypoints if p.name == name), None)
    if kp is None or not kp.validated_visible or kp.x is None or kp.y is None:
        return None
    confidence = kp.confidence if kp.confidence is not None else 0.0
    if not isfinite(kp.x) or not isfinite(kp.y) or confidence < MIN_CONFIDENCE:
        return None
    return (float(kp.x), float(kp.y), float(confidence))


def _angle(a, b, c):
    """Return projected angle ABC in degrees, or None for degenerate points."""
    if not all((a, b, c)):
        return None
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1, n2 = hypot(*v1), hypot(*v2)
    if n1 < 1e-8 or n2 < 1e-8:
        return None
    dot = max(-1.0, min(1.0, (v1[0]*v2[0] + v1[1]*v2[1])/(n1*n2)))
    from math import acos
    return round(degrees(acos(dot)), 1)


def _line_tilt(a, b):
    if not a or not b:
        return None
    dx, dy = b[0] - a[0], b[1] - a[1]
    if hypot(dx, dy) < 1e-8:
        return None
    # A line has no direction: reversing left/right endpoints must not turn a
    # nearly horizontal line into an angle near 180 degrees.
    angle = degrees(atan2(dy, dx))
    if angle > 90:
        angle -= 180
    elif angle < -90:
        angle += 180
    return round(angle, 1)


def _measurement(value, confidence, unit, interpretation):
    if value is None:
        return {"value": None, "unit": unit, "confidence": None, "status": "unavailable", "interpretation": interpretation}
    return {"value": value, "unit": unit, "confidence": round(confidence, 3), "status": "estimated_2d", "interpretation": interpretation}


def analyse_front_view(pose_assessment):
    """Attach frame-wise frontal-plane measurements and cautious observations."""
    frames = []
    for frame in pose_assessment.frames:
        p = {name: _point(frame, name) for name in (
            "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
            "left_wrist", "right_wrist", "left_hip", "right_hip",
            "left_knee", "right_knee", "left_ankle", "right_ankle")}
        def conf(*names):
            vals = [p[n][2] for n in names if p[n]]
            return min(vals) if vals else None
        shoulder_tilt = _line_tilt(p["left_shoulder"], p["right_shoulder"])
        hip_tilt = _line_tilt(p["left_hip"], p["right_hip"])
        shoulder_width = hypot(p["right_shoulder"][0]-p["left_shoulder"][0], p["right_shoulder"][1]-p["left_shoulder"][1]) if p["left_shoulder"] and p["right_shoulder"] else None
        hip_width = hypot(p["right_hip"][0]-p["left_hip"][0], p["right_hip"][1]-p["left_hip"][1]) if p["left_hip"] and p["right_hip"] else None
        ratio = round(shoulder_width/hip_width, 3) if shoulder_width and hip_width and hip_width > 1e-6 else None
        measurements = {
            "shoulder_line_tilt": _measurement(shoulder_tilt, conf("left_shoulder","right_shoulder"), "degrees", "Projected line tilt between shoulders in the image plane."),
            "hip_line_tilt": _measurement(hip_tilt, conf("left_hip","right_hip"), "degrees", "Projected line tilt between hips in the image plane."),
            "left_elbow_angle": _measurement(_angle(p["left_shoulder"],p["left_elbow"],p["left_wrist"]), conf("left_shoulder","left_elbow","left_wrist"), "degrees", "2D projected shoulder-elbow-wrist angle; not a 3D anatomical angle."),
            "right_elbow_angle": _measurement(_angle(p["right_shoulder"],p["right_elbow"],p["right_wrist"]), conf("right_shoulder","right_elbow","right_wrist"), "degrees", "2D projected shoulder-elbow-wrist angle; not a 3D anatomical angle."),
            "left_knee_angle": _measurement(_angle(p["left_hip"],p["left_knee"],p["left_ankle"]), conf("left_hip","left_knee","left_ankle"), "degrees", "2D projected hip-knee-ankle angle."),
            "right_knee_angle": _measurement(_angle(p["right_hip"],p["right_knee"],p["right_ankle"]), conf("right_hip","right_knee","right_ankle"), "degrees", "2D projected hip-knee-ankle angle."),
            "shoulder_to_hip_width_ratio": _measurement(ratio, conf("left_shoulder","right_shoulder","left_hip","right_hip"), "ratio", "Normalized image-plane shoulder width relative to hip width; perspective-sensitive."),
        }
        frames.append({"frame_number": frame.frame_number, "timestamp_seconds": frame.timestamp_seconds, "measurements": measurements})
    keys = list(frames[0]["measurements"]) if frames else []
    summary = {}
    for key in keys:
        values = [f["measurements"][key]["value"] for f in frames if f["measurements"][key]["value"] is not None]
        summary[key] = {"median": round(median(values),1) if values else None, "min": round(min(values),1) if values else None, "max": round(max(values),1) if values else None, "valid_frames": len(values), "sampled_frames": len(frames)}
    observations = []
    for key, label in (("shoulder_line_tilt","Shoulder-line tilt"),("hip_line_tilt","Hip-line tilt")):
        vals = [abs(f["measurements"][key]["value"]) for f in frames if f["measurements"][key]["value"] is not None]
        if len(vals) >= 3:
            observations.append({"title": label, "finding": f"The median absolute projected tilt was {median(vals):.1f}° across {len(vals)} measurable frames.", "type":"measured_observation", "evidence_frames":len(vals), "coach_action":"Review the annotated frames and consider whether the observed alignment is appropriate for this bowler's action.", "caveat":"This is a 2D image-plane observation, not a diagnosis or a universal technique fault."})
    return {"measurement_version": 2, "camera_profile":"end_on_batsmans_end", "coordinate_space":"normalized_2d_image_plane", "scientific_limitations":["Single-camera 2D pose cannot recover true 3D joint rotations, spinal twist, joint loading or injury risk.","The bowler approaches the camera, so perspective and apparent body scale change during the run-up.","All values depend on landmark visibility and MoveNet confidence; unavailable values are not imputed."], "frames":frames, "summary":summary, "observations":observations}
