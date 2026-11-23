"""Browser MoveNet prediction, validation, tracking, preview, and API tests."""
import json
import tempfile
from pathlib import Path
import cv2
import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from app.core.config import settings
from app.main import app
from app.pose.pose_constants import KEYPOINT_NAMES
from app.pose.browser_pose import BrowserFramePrediction, BrowserPoseSubmission
from app.pose.pose_extraction import _padded_crop, extract_pose_assessment, sample_frame_numbers
from app.pose.pose_models import Keypoint, PoseAssessment, PoseCropDiagnostics, PoseFrame
from app.pose.pose_validation import validate_keypoints
from app.pose.tracking_models import ActiveInterval, Box, TrackPoint, TrackingAssessment


def plausible_coords():
    return [(0.50,.12),(.47,.13),(.53,.13),(.42,.16),(.58,.16),(.40,.27),(.60,.27),(.30,.39),(.70,.39),(.24,.50),(.76,.50),(.44,.55),(.56,.55),(.42,.70),(.58,.70),(.40,.90),(.60,.90)]

def browser_points(confidence=0.9):
    return [{"name": n, "x": x, "y": y, "confidence": confidence} for n,(x,y) in zip(KEYPOINT_NAMES, plausible_coords())]

def validate(coords=None, confidence=0.9, previous=None, timestamp=0.5, camera_view="side"):
    coords = coords or plausible_coords()
    raw = [{"name": name, "x": xy[0], "y": xy[1], "confidence": confidence} for name, xy in zip(KEYPOINT_NAMES, coords)]
    return validate_keypoints(raw, 0.25, timestamp, previous, camera_view)

@pytest.fixture
def storage(monkeypatch):
    with tempfile.TemporaryDirectory(prefix="cbc-pose-test-", dir=Path(__file__).resolve().parents[2]) as directory:
        root=Path(directory); uploads=root/"uploads"; sessions=root/"sessions"; processed=root/"processed"
        uploads.mkdir(); sessions.mkdir(); processed.mkdir()
        monkeypatch.setattr(settings,"upload_dir",str(uploads)); monkeypatch.setattr(settings,"sessions_dir",str(sessions)); monkeypatch.setattr(settings,"processed_dir",str(processed))
        yield root,uploads,sessions,processed

def make_video(path: Path, frame_count=12, fps=10):
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*"mp4v"),fps,(320,240))
    if not writer.isOpened(): pytest.skip("OpenCV MP4V writer is unavailable on this platform.")
    for i in range(frame_count):
        frame=np.full((240,320,3),100+i,dtype=np.uint8); cv2.rectangle(frame,(20+i,30),(120+i,210),(220,220,220),3); writer.write(frame)
    writer.release()

def write_session(storage, session_id, include_video=True, valid_quality=True):
    _,uploads,sessions,_=storage
    metadata={"session_id":session_id,"bowler_name":"Synthetic Bowler","session_date":"2026-11-04","bowling_type":"fast","bowling_arm":"right","camera_view":"side","original_filename":"session.mp4"}
    (sessions/f"{session_id}.json").write_text(json.dumps(metadata),encoding="utf-8")
    if include_video: make_video(uploads/f"{session_id}.mp4")
    if valid_quality:
        quality={"session_id":session_id,"assessed_at":"2026-11-04T00:00:00Z","overall_assessment":"suitable_with_limitations","summary":"Synthetic test quality result.","metadata":{"width":320,"height":240,"fps":10,"total_frames":12,"duration_seconds":1.2,"file_size_bytes":1},"camera_view":"side","metrics":[{"name":"Video integrity","value":{"opened":True,"decodable_sample_frames":3},"status":"reliable","explanation":"Synthetic test video opened."}]}
        (sessions/f"{session_id}.quality.json").write_text(json.dumps(quality),encoding="utf-8")

def make_tracking(session_id, points=None, start=0.0, end=1.0):
    box=Box(x=.1,y=.1,width=.5,height=.8)
    track=points if points is not None else [TrackPoint(frame_number=n,timestamp_seconds=n/10,box=box,status="tracked",feature_count=5) for n in (0,5,10)]
    return TrackingAssessment(session_id=session_id,selected_at_seconds=0,selected_box=box,tracker_method="test tracker",appearance_signature=[1.0],duration_seconds=1.2,sampled_track_count=len(track),tracked_sample_count=sum(p.status=="tracked" for p in track),tracking_coverage_percent=100,tracking_interruptions=[],track=track,proposed_intervals=[],interval_detection_status="proposed",confirmed_interval=ActiveInterval(start_seconds=start,end_seconds=end,confidence="high",reason="test"),interval_source="manual",active_frame_count=2)

def write_tracking(storage, session_id):
    _,_,sessions,_=storage
    (sessions/f"{session_id}.tracking.json").write_text(make_tracking(session_id).model_dump_json(),encoding="utf-8")

@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_validation_rejects_coordinates_outside_image(bad):
    coords = plausible_coords(); coords[0] = (bad, .1)
    points, _, _, _ = validate(coords)
    assert not points[0].coordinate_valid
    assert not points[0].validated_visible
    assert points[0].raw_x == bad


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_validation_preserves_nonfinite_raw_coordinate_without_counting_visible(bad):
    coords = plausible_coords(); coords[0] = (bad, .1)
    points, _, _, _ = validate(coords)
    assert points[0].x is None
    assert not points[0].coordinate_valid and not points[0].validated_visible
    assert isinstance(points[0].raw_x, str)


def test_confidence_is_distinct_from_geometry_validation():
    points, plausible, _, _ = validate(confidence=.1)
    assert not points[0].meets_threshold
    assert plausible is None
    assert not points[0].validated_visible


def test_validation_flags_implausible_head_prediction():
    coords = plausible_coords(); coords[0] = (.5, 1.0)
    points, plausible, warnings, _ = validate(coords)
    assert points[0].anatomical_valid is False
    assert "head_too_far_from_shoulder_center" in points[0].validation_warnings
    assert plausible is False and warnings


def test_inclined_head_position_no_longer_trips_image_vertical_order_rule():
    coords = plausible_coords()
    for index, y in zip(range(5), (.45, .46, .46, .47, .47), strict=True):
        coords[index] = (coords[index][0], y)
    shoulder_y = (coords[5][1] + coords[6][1]) / 2
    shoulder_width = abs(coords[5][0] - coords[6][0])
    legacy_vertical_rule_would_reject = coords[0][1] > shoulder_y + max(.12, shoulder_width * .8)
    points, plausible, _, _ = validate(coords, camera_view="front")
    assert legacy_vertical_rule_would_reject  # Same synthetic case shows the former false rejection.
    assert plausible is True
    assert points[0].validation_state == "confident_and_valid"


def test_projected_left_right_overlap_is_ambiguous_not_anatomical_failure():
    coords = plausible_coords(); coords[5] = coords[6]
    points, plausible, warnings, _ = validate(coords, camera_view="side")
    assert plausible is True
    assert points[5].validation_state == "insufficient_evidence"
    assert points[6].validation_state == "insufficient_evidence"
    assert "left_right_projection_overlap_ambiguous" in warnings


def test_validation_flags_isolated_sudden_temporal_jump():
    prior = {i: (x, y, 0.0) for i, (x, y) in enumerate(plausible_coords())}
    coords = plausible_coords(); coords[0] = (.98, .92)
    points, plausible, warnings, _ = validate(coords, previous=prior, timestamp=.1, camera_view="front")
    assert points[0].temporal_valid is False
    assert "implausible_temporal_jump" in warnings
    assert plausible is False


def test_validation_allows_coherent_fast_whole_body_translation():
    previous_coords = plausible_coords()
    prior = {i: (x, y, 0.0) for i, (x, y) in enumerate(previous_coords)}
    moved = [(x - .20, y) for x, y in previous_coords]
    points, plausible, _, _ = validate(moved, previous=prior, timestamp=.5)
    assert plausible is True
    assert all(point.temporal_valid is not False for point in points)
    assert all(point.validated_visible for point in points)


def test_validation_allows_forward_and_sideways_trunk_inclination():
    coords = plausible_coords()
    angle = .85
    cosine, sine = np.cos(angle), np.sin(angle)
    inclined = []
    for x, y in coords:
        dx, dy = (x-.5)*.75, (y-.5)*.75
        inclined.append((.5 + cosine*dx - sine*dy, .5 + sine*dx + cosine*dy))
    points, plausible, _, _ = validate(inclined, camera_view="side")
    assert plausible is True
    assert all(point.validated_visible for point in points)


def test_validation_allows_elevated_and_asymmetric_arms():
    coords = plausible_coords()
    coords[7], coords[9] = (.34, .16), (.28, .06)
    coords[8], coords[10] = (.64, .34), (.67, .43)
    points, plausible, _, _ = validate(coords, camera_view="front")
    assert plausible is True
    assert all(points[index].validated_visible for index in (7, 8, 9, 10))


def test_one_missing_landmark_does_not_invalidate_other_landmarks():
    coords = plausible_coords()
    coords[0] = (-.1, .1)
    points, plausible, _, _ = validate(coords, camera_view="front")
    assert plausible is True
    assert points[0].validation_state == "missing_or_outside_frame"
    assert all(points[index].validated_visible for index in (5, 6, 7, 8, 11, 12, 13, 14))


def test_high_confidence_rapid_arm_motion_is_not_rejected():
    prior = {i: (x, y, 0.0) for i, (x, y) in enumerate(plausible_coords())}
    coords = plausible_coords()
    coords[9] = (.69, .50)  # Large wrist displacement in 0.1 seconds.
    points, plausible, warnings, _ = validate(coords, previous=prior, timestamp=.1, camera_view="side")
    assert plausible is not False
    assert points[9].temporal_valid is not False
    assert points[9].validation_state not in ("anatomically_implausible", "temporally_inconsistent")
    assert "implausible_temporal_jump" not in warnings


def test_temporal_threshold_uses_elapsed_time_not_frame_count():
    prior = {i: (x, y, 0.0) for i, (x, y) in enumerate(plausible_coords())}
    coords = plausible_coords(); coords[9] = (.69, .50)
    fast_points, _, fast_warnings, _ = validate(coords, previous=prior, timestamp=.05, camera_view="side")
    slow_points, _, slow_warnings, _ = validate(coords, previous=prior, timestamp=.5, camera_view="side")
    assert fast_points[9].temporal_valid is False
    assert "implausible_temporal_jump" in fast_warnings
    assert slow_points[9].temporal_valid is not False
    assert "implausible_temporal_jump" not in slow_warnings


def test_possible_left_right_swap_is_ambiguous_not_a_failure():
    prior = {i: (x, y, 0.0) for i, (x, y) in enumerate(plausible_coords())}
    coords = plausible_coords()
    coords[5], coords[6] = coords[6], coords[5]
    points, plausible, warnings, _ = validate(coords, previous=prior, timestamp=.5, camera_view="front")
    assert plausible is None
    assert "possible_left_right_swap_or_rotation" in warnings
    assert points[5].validation_state == points[6].validation_state == "insufficient_evidence"
    assert points[5].anatomical_valid is not False and points[6].anatomical_valid is not False


def test_temporary_occlusion_uses_elapsed_time_when_landmark_returns():
    coords = plausible_coords()
    raw = [{"name": name, "x": x, "y": y, "confidence": .9} for name, (x, y) in zip(KEYPOINT_NAMES, coords)]
    _, _, _, prior = validate_keypoints(raw, .25, 0., camera_view="side")
    occluded = [dict(point) for point in raw]
    occluded[0]["confidence"] = .1
    hidden_points, _, _, hidden_current = validate_keypoints(occluded, .25, .25, prior, "side")
    assert hidden_points[0].validation_state == "low_confidence"
    assert 0 not in hidden_current
    # Preserve the last valid observation for the nose across one hidden sample.
    coords[0] = (.65, .15)
    returned = [{"name": name, "x": x, "y": y, "confidence": .9} for name, (x, y) in zip(KEYPOINT_NAMES, coords)]
    returned_points, _, warnings, _ = validate_keypoints(returned, .25, .5, prior, "side")
    assert returned_points[0].temporal_valid is True
    assert "implausible_temporal_jump" not in warnings


def test_camera_view_changes_projection_checks_without_failure():
    coords = plausible_coords()
    coords[11], coords[12] = (.49, .55), (.51, .55)
    _, front_plausible, front_warnings, _ = validate(coords, camera_view="front")
    _, side_plausible, side_warnings, _ = validate(coords, camera_view="side")
    assert front_plausible is None and side_plausible is True
    assert "shoulder_hip_projection_differs_check_camera_rotation" in front_warnings
    assert "shoulder_hip_projection_differs_check_camera_rotation" not in side_warnings
    other_points, other_plausible, other_warnings, _ = validate(coords, camera_view="other")
    assert other_plausible is None
    assert "camera_view_relationships_not_assessed" in other_warnings
    assert all(other_points[index].validation_state == "insufficient_evidence" for index in (5, 6, 11, 12))


def test_empty_and_incomplete_keypoint_sequences_are_insufficient_not_errors():
    points, plausible, warnings, _ = validate_keypoints([], .25, .5, camera_view="other")
    assert len(points) == len(KEYPOINT_NAMES)
    assert plausible is None
    assert "incomplete_keypoint_sequence" in warnings
    assert all(point.validation_state == "missing_or_outside_frame" for point in points)
    partial = [{"name": name, "x": x, "y": y, "confidence": .9}
               for name, (x, y) in zip(KEYPOINT_NAMES[:10], plausible_coords()[:10])]
    points, plausible, warnings, _ = validate_keypoints(partial, .25, .5, camera_view="other")
    assert len(points) == len(KEYPOINT_NAMES)
    assert plausible is None
    assert "incomplete_keypoint_sequence" in warnings
    assert all(point.validation_state == "missing_or_outside_frame" for point in points[10:])


@pytest.mark.parametrize("fps", [24, 30, 60])
def test_sampling_denominator_and_timestamps_at_common_frame_rates(fps):
    positions, _ = sample_frame_numbers(fps * 2, fps, .5, 100, 15)
    assert positions == [0, round(fps*.5), fps, round(fps*1.5)]


def test_validation_marks_missing_landmarks_as_limited_context():
    points, plausible, warnings, _ = validate(confidence=.1)
    assert plausible is None
    assert "insufficient_confident_torso_landmarks_for_geometry_validation" in warnings
    assert all(not point.validated_visible for point in points)


def test_incorrect_landmark_prediction_is_not_corrected():
    coords = plausible_coords(); coords[0] = (1.2, .1)
    points, _, _, _ = validate(coords)
    assert points[0].x == 1.2
    assert not points[0].coordinate_valid



def test_browser_prediction_coordinates_map_from_crop_to_original_frame(storage):
    _,uploads,_,processed=storage; video=uploads/"crop-trace.mp4"; make_video(video)
    box=Box(x=.2,y=.2,width=.4,height=.5)
    tracking=make_tracking("crop-trace",[TrackPoint(frame_number=5,timestamp_seconds=.5,box=box,status="tracked",feature_count=5)],.5,.5)
    result=extract_pose_assessment("crop-trace",video,processed/"crop-trace",None,tracking,"side",{5:browser_points()})
    frame=result.frames[0]; diag=frame.crop_diagnostics
    assert frame.frame_number==5 and frame.detected
    assert diag and diag.pose_detected and diag.coordinates_mapped_to_original_frame is True
    assert diag.tracker_box==box and diag.crop is not None
    assert frame.keypoints[0].x == pytest.approx((diag.crop.left+.5*diag.crop_width)/320)
    assert frame.keypoints[0].y == pytest.approx((diag.crop.top+.12*diag.crop_height)/240)

def test_padded_crop_reports_boundary_clipping():
    crop,clipped=_padded_crop(Box(x=0,y=0,width=.2,height=.2),320,240)
    assert clipped is True and (crop.left,crop.top,crop.right,crop.bottom)==(0,0,73,52)
    inside,inside_clipped=_padded_crop(Box(x=.25,y=.25,width=.4,height=.4),320,240)
    assert inside_clipped is False and (inside.left,inside.top,inside.right,inside.bottom)==(60,50,227,165)

def test_rejected_tracker_sample_is_not_given_browser_prediction(storage):
    _,uploads,_,processed=storage; video=uploads/"lost.mp4"; make_video(video)
    box=Box(x=.1,y=.1,width=.7,height=.8)
    track=[TrackPoint(frame_number=5,timestamp_seconds=.5,box=None,status="lost",feature_count=0)]
    tracking=make_tracking("lost",track,.5,.5)
    result=extract_pose_assessment("lost",video,processed/"lost",None,tracking,"side",{})
    diag=result.frames[0].crop_diagnostics
    assert not result.frames[0].detected and diag and diag.tracker_update_accepted is False
    assert diag.crop_rejection_reason=="tracker_update_status_lost"

def test_frame_sampling_and_timestamp_preservation(storage):
    assert sample_frame_numbers(12,10,.5,60,15)[0]==[0,5,10]
    _,uploads,_,processed=storage; video=uploads/"sample.mp4"; make_video(video)
    tracking=make_tracking("sample")
    predictions={n:browser_points() for n in (0,5,10)}
    result=extract_pose_assessment("sample",video,processed/"sample",None,tracking,"side",predictions)
    assert [f.frame_number for f in result.frames]==[0,5,10]
    assert [f.timestamp_seconds for f in result.frames]==[0,.5,1.0]
    assert result.detected_frame_count==3

def test_low_confidence_browser_predictions_have_no_detected_coverage(storage):
    _,uploads,_,processed=storage; video=uploads/"low.mp4"; make_video(video)
    tracking=make_tracking("low")
    result=extract_pose_assessment("low",video,processed/"low",None,tracking,"side",{n:browser_points(.05) for n in (0,5,10)})
    assert result.detected_frame_count==0 and result.overall_detection_status=="unavailable"
    assert len(result.insufficient_detection_frames)==result.sampled_frame_count

def test_missing_torso_context_does_not_fail_independent_regions(storage):
    _,uploads,_,processed=storage; video=uploads/"partial.mp4"; make_video(video)
    points=browser_points(); points[11]["confidence"]=points[12]["confidence"]=.1
    result=extract_pose_assessment("partial",video,processed/"partial",None,make_tracking("partial"),"side",{n:points for n in (0,5,10)})
    regions={r.name:r for r in result.regions}
    assert result.detected_frame_count==3
    assert regions["upper_body"].validation_status=="limited"
    assert regions["arms"].validated_visible_frames==3

def test_pose_requires_confirmed_tracked_subject_and_uses_only_interval_frames(storage):
    _,uploads,_,processed=storage; video=uploads/"interval.mp4"; make_video(video)
    box=Box(x=.1,y=.05,width=.8,height=.9)
    track=[TrackPoint(frame_number=0,timestamp_seconds=0,box=box,status="tracked",feature_count=5),TrackPoint(frame_number=5,timestamp_seconds=.5,box=box,status="uncertain",feature_count=2),TrackPoint(frame_number=10,timestamp_seconds=1,box=box,status="tracked",feature_count=5)]
    tracking=make_tracking("interval",track,.5,1.0)
    result=extract_pose_assessment("interval",video,processed/"interval",None,tracking,"side",{10:browser_points()})
    assert [f.frame_number for f in result.frames]==[5,10]
    assert result.frames[0].detected is False and "tracker_update_status_uncertain" in result.frames[0].validation_warnings
    assert result.frames[1].detected is True
    assert result.tracking.active_frame_count==2 and result.tracking.excluded_idle_frame_count==1

@pytest.mark.asyncio
async def test_missing_session_and_video(storage):
    sid="11111111-1111-4111-8111-111111111111"
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as client:
        missing=await client.post(f"/api/sessions/{sid}/pose-assessment")
        write_session(storage,sid,include_video=False)
        no_video=await client.post(f"/api/sessions/{sid}/pose-assessment")
    assert missing.status_code==404 and no_video.status_code==404

@pytest.mark.asyncio
async def test_pose_endpoint_requires_quality_integrity_assessment(storage):
    sid="22222222-2222-4222-8222-222222222222"; write_session(storage,sid,valid_quality=False)
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as client: response=await client.post(f"/api/sessions/{sid}/pose-assessment")
    assert response.status_code==409

@pytest.mark.asyncio
async def test_pose_endpoint_requires_confirmed_subject_interval(storage):
    sid="55555555-5555-4555-8555-555555555555"; write_session(storage,sid)
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as client: response=await client.post(f"/api/sessions/{sid}/pose-assessment")
    assert response.status_code==409 and "confirm the active interval" in response.json()["detail"]

@pytest.mark.asyncio
async def test_pose_endpoint_requires_browser_predictions_for_new_assessment(storage):
    sid="66666666-6666-4666-8666-666666666666"; write_session(storage,sid); write_tracking(storage,sid)
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as client: response=await client.post(f"/api/sessions/{sid}/pose-assessment")
    assert response.status_code==422


@pytest.mark.asyncio
async def test_saved_pose_assessment_endpoint_returns_not_found_when_no_analysis_exists(storage):
    session_id = "e2f2d2a0-9bd8-4f20-94d6-40c6b1a6a7e1"
    _, _, sessions, _ = storage
    sessions.mkdir(exist_ok=True)
    (sessions / f"{session_id}.json").write_text(json.dumps({
        "session_id": session_id,
        "bowler_name": "Synthetic Bowler",
        "session_date": "2026-11-04",
        "bowling_type": "fast",
        "bowling_arm": "right",
        "camera_view": "side",
        "original_filename": "session.mp4",
    }), encoding="utf-8")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/sessions/{session_id}/pose-assessment")
    assert response.status_code == 404


def test_browser_submission_can_retain_a_sampled_frame_with_no_detected_pose():
    """A missed MoveNet frame is represented by zero-confidence landmarks, not an exception."""
    frame = BrowserFramePrediction(
        frame_number=306,
        timestamp_seconds=3.06,
        keypoints=[
            {"name": name, "x": 0.5, "y": 0.5, "confidence": 0.0}
            for name in KEYPOINT_NAMES
        ],
    )
    submission = BrowserPoseSubmission(frames=[frame])
    assert submission.frames[0].frame_number == 306
    assert all(point.confidence == 0 for point in submission.frames[0].keypoints)
