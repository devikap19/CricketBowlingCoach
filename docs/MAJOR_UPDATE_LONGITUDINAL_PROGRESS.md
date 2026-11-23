# Major update: dynamic pose guide and longitudinal bowler progress

## What changed

1. The reference skeleton now changes its illustrative arm/stride arrangement across earlier, middle and later sampled portions of the selected interval, and mirrors for left-arm bowlers.
2. The detected skeleton is fitted to its own visible validated landmark bounds, then centered and enlarged in the comparison panel.
3. Shoulder and hip lines are drawn over the detected skeleton, and selecting a frame updates the exact-frame shoulder, hip and elbow measurements.
4. The Deliveries tab now lists every saved video session for the current bowler. Earlier sessions can be reopened without overwriting their stored video or pose results.
5. The Comparison tab uses persisted metrics from all analysed videos for that bowler. It displays a chronological trend and compares the latest analysed video with the first available baseline and the preceding analysed video.
6. A backend history endpoint, `GET /api/bowlers/progress?bowler_name=...`, returns compact session summaries without returning every keypoint/frame.
7. A saved-pose endpoint, `GET /api/sessions/{session_id}/pose-assessment`, lets the frontend reopen analysed videos without rerunning MoveNet.
8. A line-angle orientation bug was fixed. A near-horizontal line now remains near 0 degrees when its endpoints are reversed. Historical assessments are recalculated to measurement version 2 when bowler history is requested.

## Interpretation boundaries

- The earlier/middle/later guide is based on sampled-frame order, not automatic detection of cricket phases.
- Shoulder/hip within-video variation is a consistency descriptor, not a validated technique score.
- Elbow/knee angle changes are descriptive and are not graded as automatically better or worse.
- The reference diagram is educational, not a scientifically validated professional action.
- The app does not claim to detect ball release, bowling legality, ball speed, accuracy or injury risk.

## Validation

- Backend tests: 69 passed, 1 skipped.
- Frontend syntax: 16 TypeScript/TSX files transpiled without syntax errors.
- Full frontend dependency installation and production build were not completed in the packaging environment.


## Follow-up coaching update

A single MoveNet no-pose result no longer aborts a full video. The browser keeps the sampled frame and submits 17 zero-confidence placeholders for the missing pose; missing joints within a partial pose are treated the same way. The backend also accepts a subset of prepared frame predictions, leaving absent frames unavailable rather than failing the entire assessment. No coordinates are inferred from neighbouring frames.

The static reference skeleton was removed. A selected-frame coach checklist now reads that frame's measured shoulder-line tilt, hip-line tilt, bowling-arm elbow angle and support-arm elbow angle. Session-level feedback uses distinct coaching cues for shoulder control, hip/base control, bowling-arm path, support-arm timing and leg movement. These remain cautious 2D observations, not a professional action model or a validated technique score.

The Deliveries and Comparison blank-screen issue was traced to the missing `historyDate` helper used by both panels after the earlier guide replacement. The helper is restored, the panels guard against incomplete history data, and a React error boundary displays a diagnostic message instead of a blank application if a future tab render fails.
