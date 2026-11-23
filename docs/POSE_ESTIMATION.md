# Pose Estimation and Visibility

Stage 3 runs single-person MoveNet Lightning on sampled video frames. The result describes detected landmarks and their visibility in those samples. It does not classify deliveries, judge bowling technique, identify a person, or calculate joint angles.

## Model and runtime

- Model: Google MoveNet SinglePose Lightning TFLite, 192 x 192 input, 17 keypoints.
- Runtime: `ai-edge-litert==2.3.0`, without installing TensorFlow or another full ML framework.
- The project development environment (Windows x86-64, CPython 3.13.7) was verified with the matching LiteRT wheel. The interpreter is initialized lazily once per API process and reused; access to the interpreter is serialized across concurrent requests.
- Model source: [Google TensorFlow Hub MoveNet Lightning TFLite model](https://tfhub.dev/google/lite-model/movenet/singlepose/lightning/tflite/float16/4?lite-format=tflite), also used in the [official TensorFlow MoveNet tutorial](https://www.tensorflow.org/hub/tutorials/movenet). The [Google MoveNet SinglePose model card](https://storage.googleapis.com/movenet/MoveNet.SinglePose%20Model%20Card.pdf) states Apache License 2.0; retain attribution and review the model card for intended-use limitations.
- The downloaded 4.76 MB model belongs at `backend/models/movenet_lightning.tflite`. It is excluded by `.gitignore`; use `python scripts/download_movenet_model.py` from `backend` to retrieve and verify the pinned SHA-256 checksum. Do not commit the model binary.

## Preprocessing and output

Each sampled OpenCV BGR frame is converted to RGB, resized to fit within a 192 x 192 square while preserving aspect ratio, and centered on a zero-valued letterbox. The current TFLite model accepts `uint8` RGB input. Its `(1, 1, 17, 3)` output is interpreted as normalized `(y, x, confidence)` points; coordinates are mapped back through the letterbox to the original frame.

Coordinates returned by the API are normalized to the original frame: `x = 0` is the left edge and `x = 1` the right; `y = 0` is the top and `y = 1` the bottom. Predictions outside `[0, 1]` are retained as raw coordinates and do not count as visible. Non-finite predictions are represented in `raw_x`, `raw_y`, or `raw_confidence` as strings (`NaN`, `Infinity`, `-Infinity`) so JSON remains valid; their numeric coordinate field is `null`. Confidence remains separate from coordinate and anatomical validity.

MoveNet keypoint order:

| Index | Name | Region |
|---:|---|---|
| 0 | Nose | Head |
| 1 | Left eye | Head |
| 2 | Right eye | Head |
| 3 | Left ear | Head |
| 4 | Right ear | Head |
| 5 | Left shoulder | Upper body |
| 6 | Right shoulder | Upper body |
| 7 | Left elbow | Arms |
| 8 | Right elbow | Arms |
| 9 | Left wrist | Arms |
| 10 | Right wrist | Arms |
| 11 | Left hip | Upper body |
| 12 | Right hip | Upper body |
| 13 | Left knee | Lower body |
| 14 | Right knee | Lower body |
| 15 | Left ankle | Lower body |
| 16 | Right ankle | Lower body |

## Sampling and coverage

- Default sampling interval: 0.5 seconds; maximum 60 sampled frames per video.
- For a valid FPS and frame count, sample zero-based frame numbers at an interval-derived stride. Long videos increase the stride as needed to respect the 60-frame cap. Timestamps are `frame_number / FPS`.
- If the container omits its frame count, read a bounded sample from the beginning using a fallback stride of 15 frames. If FPS is missing or invalid, timestamps are unavailable.
- A frame counts as a pose detection when at least four landmarks meet confidence 0.25, including at least one torso landmark (shoulder or hip) and one arm/leg landmark.
- `detected` and the existing `visible_frame_percent` fields preserve the prior confidence-based meaning for API compatibility. `raw_pose_detection_coverage_percent` names frame detection explicitly.
- `coordinate_valid` requires finite normalized coordinates inside `[0, 1]`; `confidence_valid` requires finite confidence in `[0, 1]`; `meets_threshold` means only that confidence meets the configured threshold. `validated_visible` additionally requires the applicable plausibility checks to pass. Raw prediction fields are never clamped or corrected.
- Checks use broad 2D evidence rather than ideal bowling angles or upright-body ordering. Head checks use distance from the shoulder center and face-cluster spread; a head below shoulder height alone is not rejected. Limb-segment checks use conservative projected-length bounds. A collapsed or incomplete torso is insufficient evidence, not proof of bad anatomy.
- Coincident left/right landmarks, likely label swaps, and very large limb projection changes are marked ambiguous. They do not fail the frame or invalidate unrelated joints. These can result from side-view overlap, rotation, occlusion, or projection.
- `camera_view` is coach-supplied metadata. Side view does not use shoulder/hip image-width assumptions. Front/rear views only flag extreme shoulder/hip projection differences as insufficient evidence because trunk rotation can change them. `other` skips view-dependent width checks and marks the torso relationship unassessed. No 3D reconstruction is performed.
- Temporal checks compare movement per elapsed second after subtracting robust group translation. Limits are broader for distal joints and scale with torso size; low-confidence or missing landmarks are skipped. Possible left/right swaps and large projection changes are review warnings, while only extreme isolated temporal jumps are failed. Previous valid observations are retained through temporary occlusion and the longer elapsed time is applied when a landmark returns.
- Every keypoint has a state: `confident_and_valid`, `low_confidence`, `missing_or_outside_frame`, `anatomically_implausible`, `temporally_inconsistent`, or `insufficient_evidence`. Frames separately report `validated`, `partially_validated`, `insufficient_evidence`, or `validation_failed`; lack of evidence is not an anatomical failure.
- Head, upper body, arms and lower body are assessed independently. Each region reports raw confidence visibility, validated visibility, frames with sufficient evidence, failed frames, insufficient frames, and region-specific reasons. A torso-context failure does not automatically fail the head, arms, or lower body.
- Coverage percentages use all sampled frames as their frame denominator. `anatomically_plausible_pose_coverage_percent` counts fully validated frames divided by all sampled frames; the report separately gives evidence, failed, and insufficient frame counts. Validated landmark coverage uses `17 × sampled_frame_count`; region frame coverage uses that region's sampled-frame count. Confidence-only fields continue to mean confidence threshold, not accuracy.
- `reliable`/`limited` values describe measured coverage, while pose outcomes describe validation. The dashboard shows passed, limited, failed, insufficient evidence, and not assessed separately. Raw coordinates and validation identifiers are in expandable developer diagnostics. Subject identity remains unverified by MoveNet.

Defaults can be changed through the `CBC_` settings in `backend/app/core/config.py`: `CBC_POSE_MODEL_PATH`, `CBC_POSE_SAMPLING_INTERVAL_SECONDS`, `CBC_POSE_MAX_SAMPLED_FRAMES`, `CBC_POSE_CONFIDENCE_THRESHOLD`, `CBC_POSE_MIN_REGION_FRAME_COVERAGE`, `CBC_POSE_RELIABLE_REGION_FRAME_COVERAGE`, and `CBC_POSE_FALLBACK_SAMPLE_FRAME_STRIDE`.

## Storage and API

`POST /api/sessions/{session_id}/pose-assessment` requires an existing session, video file, and saved technical quality assessment with a successful integrity check. It saves structured results separately as `storage/sessions/{session_id}.pose.json`, and saves original sampled frames plus annotated JPEG previews in `storage/processed/{session_id}/`. Response URLs use the safe route `/api/sessions/{session_id}/pose-frames/{filename}`. A cached result is reused unless `?refresh=true` is supplied.

## Limitations

- This is a single-person model. In a group or crowded frame, it may follow another person or return incorrect landmarks.
- The model's confidence is not a calibrated accuracy probability. Passing plausibility checks does not establish that coordinates are correct or biomechanically accurate. Conservative heuristics can still flag unusual but legitimate viewpoints or motion, and can miss incorrect predictions that happen to look plausible.
- Temporal validation is limited to sampled positions and available timestamps; brief motion between samples cannot be checked. When timestamps are absent, temporal validation is unavailable.
- Camera angle, cropping, distance, occlusion, clothing, lighting, motion blur, compression, and the model itself can affect detections. A missing landmark may have any of these causes.
- Sampled frames can miss brief motion. The assessment does not infer full-video continuity or delivery phases.
- Skeleton overlays preserve source frame dimensions but are JPEG previews; original decoded frames are saved separately. Overlay lines are displayed only when both endpoints pass coordinate, confidence, and validation checks.
- No accuracy or technique claim is made from the synthetic/mock tests.

## Setup and manual validation

From the `backend` directory, install the pinned runtime and download the model:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe scripts/download_movenet_model.py
```

For manual validation, use a local bowling video where the person has agreed to this processing. Start the backend and frontend, upload the clip, run **Check Video Quality**, then run **Analyse body visibility**. Inspect original/overlay pairs at early, middle, and late timestamps, compare left/right labels against the visible person, and review each region's coverage and insufficient-detection frames. Repeat with a distant, partly occluded, dim, and multi-person view to observe limitations. Synthetic tests validate the code and response behavior only; they do not establish real-world bowling-video accuracy.
