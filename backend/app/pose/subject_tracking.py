"""Fail-closed MIL tracker initialized from the coach's selected person box."""

from pathlib import Path

import cv2
import numpy as np

from app.pose.tracking_models import ActiveInterval, Box, SubjectSelection, TrackInterruption, TrackPoint, TrackingAssessment

METHOD = "OpenCV TrackerMIL object localization initialized from the coach's box, checked with an HSV appearance histogram"
SCALE_METHOD = "Lucas-Kanade optical-flow features are re-detected each frame for box-scale estimation only; they are not persistent subject tracks."


def _appearance(frame: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = box
    inset_x, inset_y = int(w * .12), int(h * .08)
    roi = frame[max(0, y+inset_y):min(frame.shape[0], y+h-inset_y), max(0, x+inset_x):min(frame.shape[1], x+w-inset_x)]
    if roi.size == 0:
        return np.zeros((16,), dtype=np.float32)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [8, 2], [0, 180, 0, 256]).flatten()
    return cv2.normalize(hist, hist).flatten()


def _pixel_box(box: Box, width: int, height: int) -> tuple[int, int, int, int]:
    x = max(0, min(int(round(box.x * width)), width-1))
    y = max(0, min(int(round(box.y * height)), height-1))
    w = max(2, min(int(round(box.width * width)), width-x))
    h = max(2, min(int(round(box.height * height)), height-y))
    return x, y, w, h


def _intervals(track: list[TrackPoint], duration: float) -> tuple[list[ActiveInterval], str]:
    valid = [p for p in track if p.status == "tracked" and p.box]
    if len(valid) < 4:
        return [], "unavailable"
    moving = [False] * len(valid)
    for i in range(1, len(valid)):
        a, b = valid[i-1].box, valid[i].box
        center = np.hypot((a.x+a.width/2)-(b.x+b.width/2), (a.y+a.height/2)-(b.y+b.height/2))
        scale = .6 * abs(a.height-b.height) + .4 * abs(a.width-b.width)
        moving[i] = center + scale >= .04
    for i in range(1, len(moving)-1):
        if moving[i-1] and moving[i+1]:
            moving[i] = True
    spans = []
    start = None
    for i, is_moving in enumerate(moving + [False]):
        if is_moving and start is None:
            start = max(0, i-1)
        elif not is_moving and start is not None:
            end = min(len(valid)-1, i)
            if end > start:
                t0 = max(0, valid[start].timestamp_seconds-.5)
                t1 = min(duration, valid[end].timestamp_seconds+.5)
                if t1-t0 >= .75:
                    spans.append((t0, t1, end-start))
            start = None
    merged = []
    for t0, t1, count in spans:
        if merged and t0-merged[-1][1] <= .75:
            merged[-1] = (merged[-1][0], t1, merged[-1][2]+count)
        else:
            merged.append((t0,t1,count))
    result = []
    for t0, t1, count in merged:
        ratio = sum(t0 <= p.timestamp_seconds <= t1 and p.status == "tracked" for p in track) / max(1, sum(t0 <= p.timestamp_seconds <= t1 for p in track))
        confidence = "high" if ratio >= .9 and count >= 5 else "medium" if ratio >= .65 else "low"
        result.append(ActiveInterval(start_seconds=round(t0,3), end_seconds=round(t1,3), confidence=confidence,
            reason="Proposed from movement of the coach-selected subject; this is not a delivery boundary detector."))
    return result, "proposed" if result else "uncertain"


def track_selected_subject(session_id: str, video_path: Path, selection: SubjectSelection) -> TrackingAssessment:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        raise ValueError("Could not open the uploaded video for subject tracking.")
    fps = float(capture.get(cv2.CAP_PROP_FPS)); frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if not np.isfinite(fps) or fps <= 0 or frame_count <= 0:
        capture.release()
        raise ValueError("Video frame rate or duration is unavailable for tracking.")
    duration = frame_count/fps
    if selection.timestamp_seconds >= duration:
        capture.release()
        raise ValueError("The selected time is beyond the end of the video.")
    capture.set(cv2.CAP_PROP_POS_FRAMES, int(round(selection.timestamp_seconds*fps)))
    ok, initial = capture.read()
    if not ok or initial is None:
        capture.release()
        raise ValueError("Could not read the selected video frame.")
    h, w = initial.shape[:2]
    scale = min(1.0, 640/max(w,h))
    size = (max(2,round(w*scale)), max(2,round(h*scale)))
    first = cv2.resize(initial,size)
    box = _pixel_box(selection.box,*size)
    if box[2] < 8 or box[3] < 12:
        capture.release()
        raise ValueError("Select the person's full body with a larger box.")
    signature = _appearance(first,box)
    tracker = cv2.TrackerMIL_create()
    tracker.init(first,box)
    prior_gray = cv2.cvtColor(first,cv2.COLOR_BGR2GRAY)
    body_scale = 1.0
    selected_size = (box[2],box[3])
    frame_no = int(round(selection.timestamp_seconds*fps))
    stride = max(1,round(fps*.25))
    track = [TrackPoint(frame_number=frame_no,timestamp_seconds=frame_no/fps,box=selection.box,
                        status="tracked",feature_count=0)]
    lost_run = 0
    identity_lost = False
    while True:
        ok, original = capture.read()
        if not ok or original is None:
            break
        frame_no += 1
        frame = cv2.resize(original,size)
        gray = cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
        timestamp = frame_no/fps
        # Estimate perspective scale from features inside the current MIL box. The full-body region
        # expands with the selected subject even though OpenCV MIL itself keeps a fixed template size.
        bx,by,bw,bh = box
        mask = np.zeros(prior_gray.shape,dtype=np.uint8)
        mask[by:by+bh,bx:bx+bw] = 255
        local_points = cv2.goodFeaturesToTrack(prior_gray,maxCorners=60,qualityLevel=.01,minDistance=3,mask=mask)
        if local_points is not None and len(local_points) >= 5:
            moved,valid,_ = cv2.calcOpticalFlowPyrLK(prior_gray,gray,local_points,None,winSize=(15,15),maxLevel=2)
            if moved is not None and valid is not None:
                source = local_points.reshape(-1,2)[valid.reshape(-1)>0]
                target = moved.reshape(-1,2)[valid.reshape(-1)>0]
                if len(source) >= 5:
                    affine,inliers = cv2.estimateAffinePartial2D(source,target,method=cv2.RANSAC,ransacReprojThreshold=2.5)
                    if affine is not None and inliers is not None and int(inliers.sum()) >= 4:
                        local_scale = float(np.hypot(affine[0,0],affine[1,0]))
                        if .97 <= local_scale <= 1.12:
                            body_scale = min(4.0,max(.8,body_scale*local_scale))
        status = "uncertain"
        distance = None
        next_box = box
        if identity_lost:
            status = "lost"
        else:
            ok_track, candidate = tracker.update(frame)
        if not identity_lost and ok_track:
            x,y,bw,bh = map(lambda v:int(round(v)), candidate)
            outside = max(0,-x)*bh + max(0,-y)*bw + max(0,x+bw-size[0])*bh + max(0,y+bh-size[1])*bw
            next_box = (max(0,x),max(0,y),min(bw,size[0]-max(0,x)),min(bh,size[1]-max(0,y)))
            if outside/max(1,bw*bh) > .45:
                status = "outside_frame"
                lost_run += 1
            else:
                distance = float(cv2.compareHist(signature,_appearance(frame,next_box),cv2.HISTCMP_BHATTACHARYYA))
                if distance <= .72:
                    status = "tracked"
                    lost_run = 0
                    box = next_box
                else:
                    lost_run += 1
        elif not identity_lost:
            lost_run += 1
        if lost_run >= 8:
            identity_lost = True
        if identity_lost:
            status = "lost"
        if frame_no % stride == 0 or frame_no == frame_count-1:
            center_x = next_box[0]+next_box[2]/2; center_y = next_box[1]+next_box[3]/2
            full_w = max(next_box[2],int(selected_size[0]*body_scale)); full_h = max(next_box[3],int(selected_size[1]*body_scale))
            full_x = int(round(center_x-full_w/2)); full_y = int(round(center_y-full_h/2))
            clipped = max(0,-full_x)*full_h + max(0,-full_y)*full_w + max(0,full_x+full_w-size[0])*full_h + max(0,full_y+full_h-size[1])*full_w
            if clipped/max(1,full_w*full_h) > .45 and status == "tracked":
                status = "outside_frame"
                lost_run += 1
            normalized = Box(x=max(0,full_x)/size[0],y=max(0,full_y)/size[1],width=min(full_w,size[0]-max(0,full_x))/size[0],height=min(full_h,size[1]-max(0,full_y))/size[1]) if status in ("tracked","uncertain") else None
            track.append(TrackPoint(frame_number=frame_no,timestamp_seconds=round(timestamp,3),box=normalized,
                status=status,feature_count=0,appearance_distance=distance))
        prior_gray = gray
    capture.release()
    interruptions=[]; start=None
    for point in track:
        if point.status != "tracked" and start is None:
            start=point.timestamp_seconds
        elif point.status == "tracked" and start is not None:
            interruptions.append(TrackInterruption(start_seconds=round(start,3),end_seconds=round(point.timestamp_seconds,3),
                reason="Tracker or appearance evidence became uncertain; the system did not substitute another person."))
            start=None
    if start is not None:
        interruptions.append(TrackInterruption(start_seconds=round(start,3),end_seconds=round(track[-1].timestamp_seconds,3),
            reason="The selected person left the frame or could not be followed; no other person was substituted."))
    proposed,status=_intervals(track,duration)
    count=sum(point.status=="tracked" for point in track)
    previous = None
    previous_appearance = None
    for point in track:
        point.appearance_distance_change = (point.appearance_distance - previous_appearance
            if point.appearance_distance is not None and previous_appearance is not None else None)
        previous_appearance = point.appearance_distance
        if point.box is not None and previous is not None:
            prev_x, prev_y, prev_w, prev_h = previous
            cur = point.box
            point.center_movement_from_previous = round(float(np.hypot((cur.x+cur.width/2)-(prev_x+prev_w/2), (cur.y+cur.height/2)-(prev_y+prev_h/2))), 5)
            point.width_scale_from_previous = round(cur.width/prev_w, 5) if prev_w else None
            point.height_scale_from_previous = round(cur.height/prev_h, 5) if prev_h else None
        if point.box is not None:
            previous = (point.box.x, point.box.y, point.box.width, point.box.height)
        else:
            previous = None
    return TrackingAssessment(session_id=session_id,selected_at_seconds=round(selection.timestamp_seconds,3),selected_box=selection.box,
        tracker_method=METHOD,scale_estimation_method=SCALE_METHOD,
        appearance_signature=[round(float(value),5) for value in signature.tolist()],duration_seconds=round(duration,3),
        sampled_track_count=len(track),tracked_sample_count=count,tracking_coverage_percent=round(count/len(track)*100,2),
        tracker_update_coverage_percent=round(count/len(track)*100,2),
        tracking_interruptions=interruptions,track=track,proposed_intervals=proposed,interval_detection_status=status)

