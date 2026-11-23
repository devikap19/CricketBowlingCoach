# CricketBowlingCoach — Product Requirements

## 1. Product Objective

Build a mobile-first cricket bowling analysis and coaching application primarily intended for coaches using smartphones.

### Core Capabilities

A coach should be able to:

1. **Upload** a cricket bowling video recorded on a smartphone.
2. **Enter session details** — bowler name, date, bowling type (fast / spin), session notes.
3. **Run an automated video quality assessment** before any technique analysis.
4. **Analyse the bowling action** based on what is reliably visible in the video.
5. **Review individual deliveries** and patterns across a six-ball session.
6. **Add coaching observations** and recommendations.
7. **Download a PDF report** and share it with the student.

The application must support both **fast bowling** and **spin bowling**.

---

## 2. Product Principles

These principles must guide all development decisions:

### 2.1 Video Quality First

- Video quality assessment **must happen before** technique analysis.
- If the video does not meet minimum quality requirements (resolution, frame rate, lighting, angle), the system must clearly communicate this to the coach and offer guidance.

### 2.2 Honest Reliability Reporting

- Do **not** report observations as reliable when the required video evidence or keypoints are insufficient.
- Each measurement must carry its own reliability status:
  - **Reliable** — Sufficient evidence to make this observation confidently.
  - **Limited** — Some evidence available, but the observation may be imprecise.
  - **Unavailable** — Insufficient evidence; do not report a value.

### 2.3 No Universal Ideals or Arbitrary Scores

- Do **not** use universal ideal joint angles.
- Do **not** generate arbitrary technique scores (e.g. "85/100") without grounded evidence.
- Technique assessment should be descriptive and evidence-based, not prescriptive.

### 2.4 Coach-Approved References (Future)

- Support coach-approved reference videos in a future stage.
- Allow comparison against a reference the coach considers appropriate for the bowler's style and development level.

### 2.5 Separation of Concerns in Analysis

- **Bowling-action analysis** (body mechanics, arm angle, follow-through) must be separated from:
  - Ball trajectory.
  - Pitch location.
  - Post-bounce movement.
- Do **not** incorrectly classify post-bounce spin or deviation as a bowling-line error.

### 2.6 Coach Authority

- Coaches must be able to **review and edit** all observations before finalising the report.
- The system provides analysis; the coach provides the coaching judgement.

### 2.7 Individual Delivery Preservation

- Preserve individual delivery results.
- Do **not** rely only on averages or aggregates — the coach needs to see each ball.

---

## 3. Intended Workflow

```
Home Dashboard
  → Upload Video
    → Enter Session Details
      → Video Quality Check
        → Analysis
          → Coaching Report
            → Download PDF
```

---

## 4. Bowling Types Supported

### Fast Bowling

- Run-up analysis (when visible).
- Delivery stride and front-foot landing.
- Arm action and release point.
- Follow-through.
- Pace consistency across deliveries.

### Spin Bowling

- Approach to the crease.
- Wrist or finger position at release (when visible).
- Release point.
- Follow-through.
- Variation detection across deliveries.

---

## 5. Technology Stack

| Layer    | Technologies                                  |
|----------|-----------------------------------------------|
| Frontend | React, Vite, TypeScript, Tailwind CSS, PWA    |
| Backend  | Python, FastAPI, OpenCV, MoveNet (future)     |
| Reports  | PDF generation (future)                       |

---

## 6. Non-Functional Requirements

- **Mobile-first** — Designed for use on smartphones in the field.
- **Installable PWA** — Works offline for basic navigation; online for analysis.
- **Performance** — Video upload and analysis should provide clear progress feedback.
- **Accessibility** — Large touch targets, clear contrast, readable typography.

---

## 7. Development Stages

### Stage 1 — Initial Setup (Current)
- Project structure and tooling.
- Frontend scaffold with Tailwind and PWA.
- Backend scaffold with health-check endpoint.

### Stage 2 — Video Upload and Quality Assessment
- Video upload with progress tracking.
- Automated quality checks (resolution, frame rate, lighting, camera angle).
- Quality feedback with actionable guidance.

### Stage 3 — Pose Estimation Integration
- MoveNet integration for keypoint detection.
- Keypoint confidence and visibility filtering.

### Stage 4 — Bowling Analysis
- Bowling-action phase detection.
- Per-delivery measurements with reliability status.
- Fast bowling and spin bowling analysis modules.

### Stage 5 — Coaching Report and PDF
- Coach review and editing interface.
- PDF report generation and download.
- Share functionality.

### Stage 6 — Reference Videos and Comparison
- Coach-approved reference video upload.
- Side-by-side or overlay comparison.

---

*This document is a living specification. It will be updated as development progresses.*
