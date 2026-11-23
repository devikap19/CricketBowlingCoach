# Coach-Selected Bowler Tracking and Active Interval

Stage 4 adds a coach-assisted single-subject workflow ahead of pose estimation. The coach pauses the uploaded video on a clear frame, draws a box around the intended bowler, tracks that selection, reviews movement-based interval proposals, and confirms or edits start/end times. Pose assessment is blocked until an interval is confirmed.

## Tracking method

OpenCV's installed `TrackerMIL` is initialized from the coach's box. An HSV color histogram from the selected region provides a conservative appearance check, and local Lucas-Kanade optical flow estimates the selected region's scale as the bowler approaches. The tracker works on a bounded-size frame copy and saves normalized boxes and status samples every 0.25 seconds. After repeated appearance/tracker failure, tracking is latched as lost; the system does not detect a replacement person or automatically switch identity. A brief interruption can recover while the MIL tracker and appearance signature remain consistent. A lost track requires a new coach selection.

The appearance histogram is a weak visual cue, not biometric identification. Similar clothing, close overlap, occlusion, camera motion, small distant subjects, and lighting changes can cause uncertain or incorrect tracking. Coaches must inspect the track and interval. When the person is too small, clipped, or ambiguous, the assessment reports limited evidence and excludes uncertain frames.

## Interval proposal

The service looks for sustained movement and scale change in the selected box, smooths a one-sample gap, and merges nearby movement bouts. It proposes possible active windows only; it does not classify run-up, delivery, or follow-through boundaries. With insufficient motion or tracking evidence, it returns no proposal. The coach can choose a proposal or enter start/end times and must confirm them. Manual changes are marked in the saved result.

This heuristic can include walking back, warm-up movement, or unrelated motion of the selected person. Multiple deliveries may appear as separate suggestions or may be combined when close together. The coach can adjust any suggested boundary. A selection made after the run-up cannot track back to earlier frames.

## Pose integration

`POST /api/sessions/{session_id}/subject-tracking` accepts `timestamp_seconds` and normalized `box` (`x`, `y`, `width`, `height`) from the coach. Tracking is saved as `storage/sessions/{session_id}.tracking.json`.

`POST /api/sessions/{session_id}/subject-interval` accepts `start_seconds` and `end_seconds` and confirms the current proposal or a coach-adjusted interval. A changed interval invalidates the saved pose assessment.

`POST /api/sessions/{session_id}/pose-assessment` now requires a confirmed tracking interval and successful technical video integrity check. It samples only that interval and runs MoveNet only where the selected subject track is considered reliable. The selected person crop is passed through the existing MoveNet preprocessing; predicted coordinates are mapped back to the original full frame for preview and validation. Lost/uncertain points are not passed to MoveNet. `tracking` in the response reports selection, tracking coverage, interruptions, interval, selected-interval sample count, excluded outside-interval count, and valid bowler pose count.

`GET /api/sessions/{session_id}/video` serves the uploaded clip inline to support seekable coach review.

## Interpretation

Video technical quality, subject tracking reliability, interval proposal, bowler pose detection, and anatomical pose validation are separate results. A coach selection is not a guarantee of identity, and successful tracking does not establish pose accuracy or technique correctness. The interval source is either `automatic` (an automatically proposed window the coach confirmed) or `manual` (coach-edited bounds). Both require explicit confirmation.
