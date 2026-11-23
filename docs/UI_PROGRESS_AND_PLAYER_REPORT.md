# UI progress dialogs and player-friendly printable report

## Processing feedback
- Bowler tracking displays a centered modal while the tracking request is running.
- Browser MoveNet analysis displays a centered modal with the current processing stage.
- On success, the modal briefly confirms completion and directs the user to the Pose analysis tab.
- Errors are shown in the same centered dialog; the existing inline error remains available in the workspace.

## Coach-first report
- The old report link in the session workspace has been replaced with a report composed in the frontend.
- Coaches can add a name, 1–5 rating, written comments, practice recommendation and optional frame reference.
- Feedback is saved through the existing session coach-feedback API and loaded again when the report is reopened.
- The report download is enabled after at least one coach review is saved and pose analysis exists.
- The browser print dialog is used to save the report as PDF.
- The printable report places coach feedback first, then session summary, evidence-based movement observations, practical suggestions, original/pose-overlay frame pairs, 2D measurements, a practice plan and limitations.
- Print CSS hides the application chrome and prints only the report on A4 pages.

## Validation
- All 16 TypeScript/TSX files passed a TypeScript transpilation syntax check.
- The backend test command did not finish within the available 55-second validation window; no new backend code was changed for this update.
- A full Vite production build was not run in this environment.
