from types import SimpleNamespace
from app.biomechanics.engine import analyse_front_view, _angle


def kp(name,x,y,c=.95):
    return SimpleNamespace(name=name,x=x,y=y,confidence=c,validated_visible=True)


def test_projected_right_angle():
    assert _angle((0,0,.9),(0,1,.9),(1,1,.9)) == 90.0


def test_front_view_analysis_reports_measurements_and_limitations():
    points=[kp('left_shoulder',.4,.3),kp('right_shoulder',.6,.3),kp('left_elbow',.35,.4),kp('left_wrist',.35,.5),kp('right_elbow',.65,.4),kp('right_wrist',.65,.5),kp('left_hip',.44,.55),kp('right_hip',.56,.55),kp('left_knee',.44,.7),kp('right_knee',.56,.7),kp('left_ankle',.43,.9),kp('right_ankle',.57,.9)]
    frame=SimpleNamespace(frame_number=10,timestamp_seconds=.5,keypoints=points)
    result=analyse_front_view(SimpleNamespace(frames=[frame]))
    assert result['camera_profile']=='end_on_batsmans_end'
    assert result['summary']['left_elbow_angle']['median'] is not None
    assert result['scientific_limitations']


def test_missing_landmarks_are_unavailable_not_imputed():
    frame=SimpleNamespace(frame_number=1,timestamp_seconds=0,keypoints=[])
    result=analyse_front_view(SimpleNamespace(frames=[frame]))
    assert result['summary']['left_elbow_angle']['median'] is None


def test_line_tilt_is_orientation_independent_and_near_horizontal_is_near_zero():
    from app.biomechanics.engine import _line_tilt
    left_to_right = _line_tilt((0.8, 0.4, 0.9), (0.2, 0.401, 0.9))
    right_to_left = _line_tilt((0.2, 0.401, 0.9), (0.8, 0.4, 0.9))
    assert left_to_right is not None and abs(left_to_right) < 1
    assert right_to_left == left_to_right


def test_line_tilt_returns_unavailable_for_coincident_points():
    from app.biomechanics.engine import _line_tilt
    assert _line_tilt((0.5, 0.5, 0.9), (0.5, 0.5, 0.9)) is None
