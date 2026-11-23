# CricketBowlingCoach 🏏

A web application for analysing cricket bowling videos using **browser-based MoveNet pose estimation** and a **Python/FastAPI analysis backend**.

The application helps review a bowler's movement by selecting and tracking the bowler, confirming the delivery interval, detecting body landmarks, and generating pose-based measurements, visualisations, and feedback.

## Features

- Upload bowling videos and assess basic video quality
- Select the bowler and track the selected subject
- Review and confirm the active bowling/delivery interval
- Run MoveNet Lightning pose estimation in the browser using TensorFlow.js
- Transfer keypoint coordinates and confidence scores to the backend
- Map crop-relative keypoints back to the original video frame
- Validate pose landmarks and calculate pose-based measurements
- View annotated pose previews, results, and feedback
- Reopen saved sessions

## Technology stack

| Layer | Technologies |
| --- | --- |
| Frontend | React, TypeScript, Vite |
| Browser pose inference | TensorFlow.js, MoveNet Lightning |
| Backend API | Python 3.11, FastAPI, Uvicorn |
| Video processing | OpenCV |
| Validation and data models | Pydantic |
| Testing | pytest |

> **Note:** MoveNet inference runs in the **browser**, not in the Python backend. You do **not** need `ai-edge-litert` or a backend `.tflite` model file.

## Prerequisites

Install the following before starting:

- [Git](https://git-scm.com/downloads)
- [Python 3.11](https://www.python.org/downloads/) (ensure `python` works in a terminal)
- [Node.js and npm](https://nodejs.org/) (use a version supported by the project's Vite installation)
- A modern browser such as Chrome or Edge, preferably with WebGL support

The commands below are for **Windows PowerShell**. Keep the backend and frontend running in separate terminals.

## Getting started

### 1. Clone the repository

```powershell
git clone https://github.com/devikap19/CricketBowling.git
cd CricketBowling
```

If the repository is private, ask the owner to add your GitHub account as a collaborator and accept the invitation before cloning.

### 2. Install backend dependencies

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Using the virtual environment's Python executable directly avoids PowerShell activation-policy issues.

### 3. Start the backend

In the **same backend terminal**:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The API should be available at:

- API: http://127.0.0.1:8000
- Interactive API docs: http://127.0.0.1:8000/docs

**Keep this terminal running.**

### 4. Install frontend dependencies

Open a **second PowerShell terminal**, navigate to the cloned repository, then:

```powershell
cd frontend
npm.cmd ci
```

`npm.cmd` is used instead of `npm` because some Windows PowerShell configurations block `npm.ps1`.

### 5. Start the frontend

In the frontend terminal:

```powershell
npm.cmd run dev
```

Open the local address shown by Vite, normally:

**http://localhost:5173**

Keep the backend running at the same time.

## How to use

1. Open the web application.
2. Upload a cricket bowling video and enter the session details.
3. Run the video quality check.
4. Select the bowler to track.
5. Review the tracking results and confirm the delivery interval.
6. Start pose assessment. The browser loads MoveNet and processes the prepared crops.
7. Review pose landmarks, measurements, annotated previews, and available feedback.
8. Revisit saved sessions from the application when needed.

## How the analysis works

```text
Bowling video
    ↓
Video quality assessment
    ↓
Bowler selection and subject tracking
    ↓
Confirmed delivery interval
    ↓
Backend prepares tracked-bowler image crops
    ↓
Browser runs TensorFlow.js MoveNet Lightning
    ↓
17 pose keypoints + confidence scores per sampled frame
    ↓
Backend maps keypoints to original-frame coordinates
    ↓
Landmark validation, measurements and feedback
    ↓
Annotated previews and session results
```

## Project structure

```text
CricketBowling/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI endpoints
│   │   ├── core/           # Application configuration
│   │   ├── pose/           # Tracking, crops, validation and analysis
│   │   └── video/          # Video quality assessment
│   ├── tests/              # Backend tests
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/       # API calls and browser MoveNet inference
│   │   └── types/
│   ├── package.json
│   └── package-lock.json
├── docs/                   # Technical and product documentation
├── storage/                # Local session/video output (not committed)
└── README.md
```

## Testing

### Backend

From `backend/`, with the virtual environment created:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

### Frontend production build

From `frontend/`:

```powershell
npm.cmd run build
```

The build may show a bundle-size warning; this does not necessarily mean the build failed.

## Troubleshooting

**`npm.ps1 cannot be loaded because running scripts is disabled`**  
Use `npm.cmd` instead of `npm`, for example `npm.cmd run dev`.

**PowerShell blocks virtual-environment activation**  
Use `backend\.venv\Scripts\python.exe` directly, as shown in the setup commands. Activation is optional.

**`python` is not recognised or the wrong Python version is used**  
Install Python 3.11 and verify with `python --version`. On Windows, `py -3.11` may also be available.

**Frontend opens but API calls fail**  
Confirm the backend is running on port **8000** and the frontend is running on **localhost:5173**. Check the browser console and backend terminal for errors. The backend's default CORS configuration expects `http://localhost:5173`.

**Browser pose estimation is slow or fails**  
Use an up-to-date Chrome or Edge browser and check WebGL availability. Initial model loading can take longer than subsequent runs. Open the browser developer console for detailed errors.

**Uploads or sessions are missing on a fresh clone**  
This is expected: personal videos and generated session files are intentionally excluded from Git. Upload a new video to create a new session. If a required storage directory is absent, create it under `storage/`.

**Port 8000 or 5173 is already in use**  
Stop the conflicting process. If you change ports, update the corresponding frontend API URL or backend CORS configuration as needed.

## Notes for collaborators

- Do not commit `.env` files, virtual environments, `node_modules`, uploaded videos, or generated reports.
- Install Python dependencies from the project-root `requirements.txt` (which includes `backend/requirements.txt`), or directly from `backend/requirements.txt`. and frontend dependencies from `frontend/package-lock.json`.
- Create a feature branch before making major changes and open a pull request when ready.
- The browser-based MoveNet implementation is the active inference path; the old Python LiteRT implementation has been removed.

## Current validation

For this packaged revision, the backend test suite completed with **69 passed, 1 skipped**. All 16 frontend TypeScript/TSX source files passed a TypeScript transpilation syntax check. A full Vite production build was not verified in the packaging environment because npm dependency installation timed out; run `npm.cmd ci` and `npm.cmd run build` on the development machine after extraction.

## Repository

https://github.com/devikap19/CricketBowling

## Front-view biomechanics and coach review

The application includes a confidence-aware, end-on (batsman's-end) 2D biomechanics layer. It calculates projected shoulder/hip line tilt, elbow and knee angles, and shoulder-to-hip image-width ratio from validated MoveNet landmarks. These are image-plane estimates, not 3D anatomical measurements. Missing landmarks are reported as unavailable rather than imputed.

After pose assessment, the workspace displays available measurements and interpretation limitations. In the Report tab, coaches can save a 1–5 rating, comments and recommendations. A printable session report is available at `GET /api/sessions/{session_id}/report`; use the browser print dialog to save it as PDF. Coach feedback endpoints are `GET` and `POST /api/sessions/{session_id}/coach-feedback`.

See [Front-view biomechanics](docs/FRONT_VIEW_BIOMECHANICS.md) for methodology and limitations. Automated ball-release detection, validated phase segmentation, 3D biomechanics and injury-risk assessment are not claimed by this version.


## Recent workspace improvements

- Pose sample images (original frame and MoveNet skeleton overlay) can be clicked to open a larger view.
- Pose analysis now includes plain-language coaching interpretation based on the backend's biomechanics observations and coach actions. It deliberately avoids claiming a universal ideal action or promising speed/accuracy gains.
- **Deliveries / video history** lists every saved video session for the same bowler in date order. Selecting an earlier recording reopens its video and saved tracking/analysis workflow. Individual ball-release segmentation is still not implemented.
- **Comparison** loads the bowler's persisted pose summaries across all uploaded sessions. It compares the first analysed recording (baseline), the previous recording, and the latest recording. Shoulder/hip within-video variation is used as a consistency observation; elbow/knee medians are shown as changes only, not graded as better or worse.

These additions use the existing pose/tracking data. No new inference model, ball-release detector, delivery segmentation, or external reference dataset has been added.


## Beginner-friendly movement interpretation (major update)

Pose Analysis now includes a beginner-friendly report based on the measured front-view biomechanics:
- Shoulder and hip line changes are described as within-clip consistency cues.
- Elbow and knee angles are explained as observed 2D ranges, not ideal target angles.
- Each insight includes what was measured, what to review or try, why it may help, and how many frames support it.
- A selectable sampled frame displays the actual validated MoveNet skeleton next to a schematic end-on alignment reference.
- The Comparison tab combines these coaching insights with minimum, median and maximum measured values.
- A short plain-English guide explains the general bowling action stages.

The reference skeleton is an educational alignment diagram, not a validated ideal bowling action or professional-player comparison. The shoulder/hip variation bands are clip-review heuristics only, not cricket technique standards. The app does not infer ball release, true 3D mechanics, bowling legality, pace, accuracy or injury risk. Confirm technique changes with a qualified cricket coach.


## Longitudinal bowler history and comparison (latest update)

- Every upload remains an independent saved session. Sessions are grouped by bowler name (case-insensitive) and are not overwritten when another video is uploaded.
- `GET /api/bowlers/progress?bowler_name=...` returns the bowler's chronological session list and compact persisted biomechanics summaries. Full pose frames are not returned by this history endpoint.
- `GET /api/sessions/{session_id}/pose-assessment` loads a saved assessment when reopening a video, so a previously analysed session does not need to rerun MoveNet just to view its results.
- The Deliveries tab now acts as a bowler-specific video history: it shows each recording, date, analysis status and a control to reopen an earlier recording.
- The Comparison tab compares all analysed recordings in chronological order, displays metric trends, compares the latest recording with the first available baseline and with the previous recording, and reports missing measurements rather than inventing values.
- Shoulder/hip line variation is described as within-recording consistency only. Elbow/knee angle changes are descriptive. Neither is a validated cricket technique score or proof of improvement.
- The reference skeleton now changes its illustrative arm/stride pose across earlier, middle and later portions of the selected clip and mirrors for left-arm bowlers. It is a movement-stage illustration, not a scientifically validated ideal delivery phase.
- The detected skeleton is automatically fitted to the visible validated landmark bounds, centred and enlarged. Shoulder and hip alignment lines are drawn on the detected pose; frame-specific 2D measurements update with the selected timestamp.
- A line-angle orientation bug was corrected: reversing left/right endpoints no longer turns a near-horizontal line into a value near 180 degrees. Historical stored assessments are migrated to measurement version 2 when bowler progress is requested.

The stage labels are based on the order of sampled frames, not an automated detection of gather, front-foot contact, release or follow-through. Use the reference as an educational visual aid and confirm technique changes with a qualified coach.


## Latest coaching and missed-frame handling update

- MoveNet inference now continues when a sampled crop has no detected pose. That moment is retained with zero-confidence landmarks, and the remaining frames are still analysed. A missed frame is not silently replaced with a guessed skeleton.
- The backend accepts a partial set of browser predictions as a fallback; unsubmitted prepared frames remain in the output with unavailable pose evidence.
- The detected skeleton visual can show coordinate-valid provisional landmarks for visual review, while biomechanical calculations continue to use only landmarks that pass validation.
- The previous illustrative stick-figure reference has been replaced by a frame-specific coach checklist. It reads the selected moment's shoulder, hip, bowling-arm and support-arm measurements and gives different plain-English cues.
- Coaching insights now distinguish shoulder control, hip/base control, bowling-arm path, support-arm timing and leg/stride control. Advice is measurement-dependent and does not claim that one fixed joint angle is universally ideal.
- The blank Deliveries/Comparison tab issue was caused by the missing `historyDate` helper referenced by both panels. The helper has been restored. A tab-level React error boundary now shows a diagnostic message instead of taking down the whole workspace if another render error occurs.
- Delivery history and comparisons tolerate incomplete/older session history records rather than assuming every optional field exists.


## Latest UI and printable-report update

- Bowler tracking and MoveNet pose analysis now use a centered processing dialog. The dialog closes automatically after success and tells the player to open Pose analysis for results.
- The old report link is replaced in the workspace by a coach-first, player-friendly report page.
- Coaches can save feedback and ratings to the session. After at least one coach review is saved and pose analysis exists, the report can be printed or saved as PDF using the browser print dialog.
- The report includes coach feedback first, session summary, plain-English movement observations and practice suggestions, original frame/skeleton pairs, measured 2D values, a simple practice plan and camera limitations.
