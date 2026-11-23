# Video Quality Assessment Criteria

This document describes the initial, technical checks performed by `POST /api/sessions/{session_id}/quality-check`. These thresholds are configurable heuristics for triage. They are not scientifically validated cutoffs and do not guarantee pose-estimation or coaching accuracy.

## Metrics

| Metric | Measurement and initial threshold | Reliability and interpretation |
|---|---|---|
| Video integrity | OpenCV must open the saved file and decode at least one sampled frame. | `reliable` when opened and at least one frame decodes; otherwise `unavailable`. A failed integrity check makes the assessment not suitable. |
| Video metadata | Width, height, container-reported FPS and frame count, duration (`frame_count / FPS`), and file size. | Individual invalid values such as zero FPS or frame count are returned as unavailable (`null`). Metadata reliability requires readable dimensions. Duration is omitted when FPS or frame count is invalid. |
| Resolution | Orientation-independent minimum: shorter dimension at least 360 pixels and longer dimension at least 640 pixels. | `reliable` when dimensions are read. Below the minimum is not suitable for the current initial-analysis gate. More pixels do not prove that the bowler or joints are visible. |
| Frame rate | Minimum 24 FPS. | `reliable` when the container reports a positive finite FPS. Lower or invalid FPS is not suitable for initial analysis. Variable frame rate and motion sharpness are not determined from this metadata. |
| Brightness and lighting | Up to 12 frames are sampled across the clip. For grayscale pixel values 0-255, report mean brightness and percentages at or below 40 (very dark) and at or above 220 (very bright). A warning threshold is 35% of sampled pixels in either extreme. | `reliable` with at least 6 samples; `limited` with 3-5; otherwise `unavailable`. The 35% threshold is a coarse image-wide warning and may miss a dark or overexposed subject against a normally exposed background. A warning makes the video not suitable pending review. |
| Motion blur / sharpness | Compute variance of the Laplacian for each sampled grayscale frame; report average and lowest value. Lowest value below 60 triggers a warning. | `reliable` with at least 6 samples; `limited` with 3-5; otherwise `unavailable`. This content-dependent heuristic cannot distinguish motion blur from focus, texture, compression, or a naturally smooth background. A warning makes the video not suitable pending review. |
| Camera stability | Track visual features between adjacent sampled frames with Lucas-Kanade optical flow and estimate a robust global affine transform with RANSAC. Report tracked pair count, median global shift, and median inlier fraction. | Always `limited` when an estimate exists because subject motion, pan, zoom, and scene texture cannot be reliably separated at this stage. `unavailable` when too few features can be tracked. A shift above 5 pixels per sampled pair prompts coach review; it does not automatically classify the camera as unstable. |
| Bowler visibility | Not measured. | `unavailable`; no automatic full-body visibility assessment is implemented. |
| Pose coverage | Not measured. | `unavailable`; pose estimation and joint visibility are not implemented. |

The sample minimum defaults to 3 frames. Fewer samples leave lighting and blur unavailable and make the overall assessment not suitable.

## Overall assessment rules

- **Not suitable for analysis** when the video cannot be opened or sampled adequately, is below the resolution or FPS minimum, or triggers the lighting or sharpness warning.
- **Suitable with limitations** when the technical minimums pass but a core measurement has limited or unavailable reliability.
- **Suitable for initial analysis** when the technical minimums pass and the core technical measurements are reliable. Camera movement is inherently limited, and bowler visibility and pose coverage are unavailable; this label does not imply those properties were checked.

No numerical quality score is calculated. Each metric is reported independently with its own status and explanation so one result does not hide another.

## Configurable settings

Set these environment variables for the FastAPI process (the `CBC_` prefix is configured in `backend/app/core/config.py`):

| Setting | Default |
|---|---:|
| `CBC_QUALITY_MIN_WIDTH` | 640 |
| `CBC_QUALITY_MIN_HEIGHT` | 360 |
| `CBC_QUALITY_MIN_FPS` | 24.0 |
| `CBC_QUALITY_DARK_PIXEL_THRESHOLD` | 40 |
| `CBC_QUALITY_BRIGHT_PIXEL_THRESHOLD` | 220 |
| `CBC_QUALITY_MAX_EXTREME_PIXEL_FRACTION` | 0.35 |
| `CBC_QUALITY_MIN_BLUR_VARIANCE` | 60.0 |
| `CBC_QUALITY_MIN_DECODABLE_SAMPLES` | 3 |

## Limitations

- Assessment uses container metadata and a maximum of 12 sampled frames, not every frame.
- MP4/MOV codec/container behavior can affect seeking and metadata accuracy.
- Lighting and Laplacian blur thresholds are heuristics and vary with scene content, camera processing, and compression.
- Camera movement estimation cannot confidently distinguish a moving bowler from camera motion in every scene; ambiguous cases remain limited or unavailable.
- The coach-selected camera view is stored as metadata only. This stage does not determine whether the camera angle suits a particular measurement.
- The system does not assess full-body or joint visibility, pose quality, action correctness, delivery segmentation, ball trajectory, pitch location, or post-bounce movement.
