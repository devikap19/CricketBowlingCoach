# Front-view biomechanics and coaching module

## Camera profile
The supported analysis profile is an end-on view from the batsman's end, with the camera behind/near the batting stumps looking down the pitch towards the bowler. The bowler approaches the camera.

## Measurements
The biomechanics engine derives confidence-aware 2D image-plane measurements from the validated MoveNet keypoints: shoulder-line tilt, hip-line tilt, left/right projected elbow angles, left/right projected knee angles, and shoulder-to-hip image-width ratio. It reports frame-level values and median/minimum/maximum summaries over available frames. Missing or low-confidence landmarks produce unavailable measurements; values are not interpolated.

## Interpretation
These values are not 3D anatomical measurements. A single end-on camera cannot reliably recover depth, true 3D joint rotation, spinal twist, joint loading, injury risk, or legal bowling action. The bowler approaches the camera, so perspective and apparent body scale vary. The shoulder-to-hip width ratio is especially perspective-sensitive. Coaches must interpret observations alongside the original video and their own assessment.

## Technique observations
The initial observation layer describes measurable projected alignment patterns and asks the coach to review them. It does not label a pattern as universally correct/incorrect or diagnose a fault. Cricket-specific thresholds should only be added when supported by an appropriate published source and validated for this camera setup and population.

## Coach feedback
`POST /api/sessions/{session_id}/coach-feedback` stores a coach name, 1–5 rating, comment, optional delivery frame number, recommendation and timestamp in the session metadata directory. `GET` returns the saved feedback.

## Session report
`GET /api/sessions/{session_id}/report` produces a printable HTML report. Use the browser's Print > Save as PDF to export it. The report includes session metadata, pose coverage, biomechanics summaries, cautious observations, feedback and limitations.

## Known scope limitations
- No automated ball-release detector or independently validated bowling-phase segmentation is included.
- No 3D reconstruction or medical/injury assessment is provided.
- The current measurements are projected 2D geometric descriptors, not validated coaching scores.
- Feedback is session-level unless the coach supplies a frame number.


## Beginner-friendly coaching and reference comparison

The Pose Analysis and Comparison views now translate the measured front-view data into plain-language coaching prompts:
- Shoulder-line and hip-line measurements are described as clip-level consistency observations.
- Elbow and knee angles are reported as observed 2D ranges, without treating a single angle as universally correct.
- Each insight includes the measured observation, a cautious next step, a possible benefit, and the amount of supporting frame evidence.
- A selectable sampled frame shows the validated MoveNet skeleton beside a simple front-view alignment guide with level shoulder/hip lines.

The guide is deliberately an educational alignment reference, not a complete ideal bowling action or a professional-player benchmark. The green/amber/grey insight categories are review cues, not a technique grade. Shoulder/hip consistency bands (range <= 8 degrees, > 15 degrees, and the middle band) are heuristic descriptions of variation within this recording only; they are not published cricket coaching thresholds and must not be interpreted as pass/fail standards. Elbow and knee angles are descriptive only because their expected values change throughout the delivery.

The five written action stages (approach, delivery stride, front-foot contact, bowling arm action and follow-through) are general learning prompts. The application does not claim to have detected these exact phases or ball release. It uses the sampled frame sequence order for the selectable visual comparison.

The detected skeleton uses only validated visible keypoints. Missing joints are omitted rather than estimated. The reference skeleton is a schematic illustration and should not be used to prescribe a bowler's individual technique. Benefits such as improved balance or repeatability are possible coaching aims, not measured outcomes; the application does not predict pace, accuracy, legality or injury risk.


## Longitudinal session comparison and display

Each video upload is retained as its own session. The bowler progress endpoint returns chronological sessions with compact persisted biomechanics summaries. Shoulder and hip line variation across sampled frames can be compared as a within-video consistency cue. Elbow and knee median angles are displayed as descriptive changes only; a larger or smaller angle is not automatically better. The interface compares the latest analysed video with both the first available baseline and the preceding analysed video.

A near-horizontal shoulder/hip line is now represented consistently regardless of which endpoint is treated as the first point. The line orientation is normalized into the interval [-90°, 90°], avoiding false values close to 180°. Historical pose records with older biomechanics metadata are recalculated when bowler history is requested.

The visual reference changes its illustrative arm/stride arrangement across earlier, middle and later sampled portions and mirrors for left-arm bowlers. These labels are temporal positions within the selected interval, not detected cricket delivery phases. The actual pose display is cropped to its validated landmark bounds and centered; actual shoulder and hip lines are overlaid for frame-specific review.
