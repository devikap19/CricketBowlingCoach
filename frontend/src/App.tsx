
import { useCallback, useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from 'react';
import { AppNavigation, PageHeader, type AppRoute } from './components/AppNavigation';
import { VideoWorkspace } from './components/VideoWorkspace';
import { WorkflowProgress } from './components/WorkflowProgress';
import { useHealth } from './hooks/useHealth';
import { BowlersPage, DashboardPage, ReportsPage, SessionsPage } from './pages/CollectionPages';
import { SessionWorkspacePage } from './pages/SessionWorkspace';
import {
  assessPoseWithBrowserPredictions,
  checkVideoQuality,
  confirmSubjectInterval,
  getBrowserPoseCrops,
  getSubjectTracking,
  listSessions,
  trackSubject,
  uploadSession,
  getBowlerProgress,
  getSavedPoseAssessment,
} from './services/api';
import { runBrowserPoseInference } from './services/browserPose';
import type {
  BowlingArm,
  BowlingType,
  CameraView,
  PoseAssessment,
  QualityAssessment,
  SessionUploadResponse,
  TrackBox,
  TrackingAssessment,
  BowlerProgressResponse,
} from './types';

const MAX_VIDEO_SIZE = 200 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = ['.mp4', '.mov'];

function localToday() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

function App() {
  const { health } = useHealth();

  const [route, setRoute] = useState<AppRoute>('dashboard');
  const [sessions, setSessions] = useState<SessionUploadResponse[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState<string | null>(null);

  const [session, setSession] = useState<SessionUploadResponse | null>(null);
  const [quality, setQuality] = useState<QualityAssessment | null>(null);
  const [tracking, setTracking] = useState<TrackingAssessment | null>(null);
  const [pose, setPose] = useState<PoseAssessment | null>(null);
  const [bowlerHistory, setBowlerHistory] = useState<BowlerProgressResponse | null>(null);

  const [workflowStep, setWorkflowStep] = useState(1);
  const [bowlerName, setBowlerName] = useState('');
  const [sessionDate, setSessionDate] = useState(localToday);
  const [bowlingType, setBowlingType] = useState<BowlingType>('fast');
  const [bowlingArm, setBowlingArm] = useState<BowlingArm>('right');
  const [cameraView, setCameraView] = useState<CameraView>('side');
  const [notes, setNotes] = useState('');

  const [video, setVideo] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [analysisProgress, setAnalysisProgress] = useState<string | null>(null);
  const [processingNotice, setProcessingNotice] = useState<{ message: string; done?: boolean; error?: boolean } | null>(null);

  const refreshSessions = useCallback(async () => {
    setSessionsError(null);

    try {
      const saved = await listSessions();
      setSessions(saved);
    } catch {
      setSessionsError('Saved sessions could not be loaded. Check that the service is available.');
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshSessions();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [refreshSessions]);

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  useEffect(() => {
    if (!processingNotice?.done && !processingNotice?.error) return;
    const timer = window.setTimeout(() => setProcessingNotice(null), processingNotice.error ? 4200 : 3600);
    return () => window.clearTimeout(timer);
  }, [processingNotice]);

  const knownBowlers = useMemo(
    () => [...new Map(
      sessions.map((item) => [
        item.bowler_name.trim().toLocaleLowerCase(),
        item.bowler_name,
      ]),
    ).values()],
    [sessions],
  );

  function navigate(next: AppRoute) {
    if (next === 'new-session') {
      startNewSession();
    } else {
      setRoute(next);
    }
  }

  function startNewSession() {
    setSession(null);
    setQuality(null);
    setTracking(null);
    setPose(null);
    setBowlerHistory(null);
    setWorkflowStep(1);

    setBowlerName('');
    setSessionDate(localToday());
    setBowlingType('fast');
    setBowlingArm('right');
    setCameraView('side');
    setNotes('');

    setVideo(null);
    setPreviewUrl((current) => {
      if (current) URL.revokeObjectURL(current);
      return null;
    });

    setUploadProgress(0);
    setError(null);
    setWorkspaceError(null);
    setAnalysisProgress(null);
    setProcessingNotice(null);
    setRoute('new-session');
  }

  function selectVideo(file: File | null) {
    setPreviewUrl((current) => {
      if (current) URL.revokeObjectURL(current);
      return file ? URL.createObjectURL(file) : null;
    });

    setVideo(file);
  }

  function chooseVideo(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0];
    event.target.value = '';
    setError(null);

    if (!selected) return;

    const extension = selected.name.slice(selected.name.lastIndexOf('.')).toLowerCase();

    if (!ACCEPTED_EXTENSIONS.includes(extension)) {
      setError('Choose an MP4 or MOV video.');
      return;
    }

    if (selected.size <= 0) {
      setError('This video is empty. Choose another file.');
      return;
    }

    if (selected.size > MAX_VIDEO_SIZE) {
      setError('This video is larger than the 200 MB upload limit.');
      return;
    }

    selectVideo(selected);
  }

  function continueFromDetails(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!bowlerName.trim()) {
      setError('Enter or select a bowler name.');
      return;
    }

    if (!sessionDate) {
      setError('Choose a session date.');
      return;
    }

    setError(null);
    setWorkflowStep(2);
  }

  async function uploadAndContinue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!video) {
      setError('Choose a video before continuing.');
      return;
    }

    if (!health) {
      setError('The session service is unavailable. Try again when it is ready.');
      return;
    }

    const data = new FormData();

    data.append('video', video);
    data.append('bowler_name', bowlerName.trim());
    data.append('session_date', sessionDate);
    data.append('bowling_type', bowlingType);
    data.append('bowling_arm', bowlingArm);
    data.append('camera_view', cameraView);

    if (notes.trim()) {
      data.append('notes', notes.trim());
    }

    setBusy(true);
    setError(null);
    setUploadProgress(0);

    try {
      const uploaded = await uploadSession(data, setUploadProgress);

      setSession(uploaded);
      setQuality(null);
      setTracking(null);
      setPose(null);
      setBowlerHistory(await getBowlerProgress(uploaded.bowler_name).catch(() => null));
      setWorkflowStep(3);

      void refreshSessions();
    } catch {
      setError('The video could not be uploaded. Check that it is a playable MP4 or MOV under 200 MB, then try again.');
    } finally {
      setBusy(false);
    }
  }

  async function runTracking(time: number, box: TrackBox) {
    if (!session) return;

    setBusy(true);
    setError(null);
    setPose(null);
    setProcessingNotice({ message: 'Tracking the bowler across the video…' });

    try {
      const result = await trackSubject(session.session_id, time, box);

      setTracking(result);
      setWorkflowStep(4);
      setProcessingNotice({ message: 'Bowler tracking is ready. You can review the tracked movement now.', done: true });
    } catch {
      setError('The bowler could not be followed from that selection. Return to the video, choose a clear frame, and redraw the box.');
      setProcessingNotice({ message: 'Tracking could not be completed. Please choose a clearer frame and try again.', error: true });
    } finally {
      setBusy(false);
    }
  }

  async function confirmInterval(start: number, end: number) {
    if (!session) return;

    setBusy(true);
    setError(null);

    try {
      setTracking(await confirmSubjectInterval(session.session_id, start, end));
    } catch {
      setError('That interval could not be saved. Choose a range that includes a tracked part of the video.');
    } finally {
      setBusy(false);
    }
  }

  function redrawSelection() {
    setTracking(null);
    setPose(null);
    setError(null);
    setWorkflowStep(3);
  }

  /**
   * Complete pose analysis using browser-side TensorFlow.js MoveNet.
   *
   * Python prepares the cropped images.
   * The browser runs MoveNet on those images.
   * Python receives the predictions and calculates the final assessment.
   */
  async function runBrowserAnalysis(sessionId: string): Promise<PoseAssessment> {
    setAnalysisProgress('Preparing the selected bowler frames…');

    const crops = await getBrowserPoseCrops(sessionId);

    if (!crops.length) {
      throw new Error('No usable bowler frames were prepared for pose analysis.');
    }

    setAnalysisProgress(`Loading MoveNet and analysing ${crops.length} frames…`);

    const predictions = await runBrowserPoseInference(
      crops,
      (completed, total) => {
        setAnalysisProgress(`Running MoveNet in your browser: ${completed}/${total} frames`);
      },
    );

    setAnalysisProgress('Sending predictions to Python for analysis…');

    const assessment = await assessPoseWithBrowserPredictions(
      sessionId,
      predictions,
      true,
    );

    setAnalysisProgress(null);

    return assessment;
  }

  async function continueToAnalysis() {
    if (!session || !tracking?.confirmed_interval) return;

    setBusy(true);
    setWorkspaceError(null);
    setAnalysisProgress('Preparing pose analysis…');
    setProcessingNotice({ message: 'Preparing the selected frames for MoveNet…' });
    setRoute('session-workspace');

    try {
      const qualityResult = quality ?? await checkVideoQuality(session.session_id);

      setQuality(qualityResult);

      const integrityPassed = qualityResult.metrics.some(
        (metric) =>
          metric.name === 'Video integrity' &&
          metric.status === 'reliable' &&
          metric.value?.opened === true,
      );

      if (!integrityPassed) {
        setWorkspaceError('The video could not be read clearly enough to continue to pose analysis.');
        setProcessingNotice({ message: 'The video check found a problem. Review the recording before running pose analysis.', error: true });
        return;
      }

      const assessment = await runBrowserAnalysis(session.session_id);
      setPose(assessment);
      setBowlerHistory(await getBowlerProgress(session.bowler_name).catch(() => null));
      setProcessingNotice({ message: 'Pose analysis is complete. Go to the Pose analysis section to view your results.', done: true });
    } catch (analysisError) {
      console.error('Browser pose analysis failed:', analysisError);

      const message = analysisError instanceof Error
        ? analysisError.message
        : 'The visual review could not be completed. The saved video and tracking result are still available.';
      setWorkspaceError(message);
      setProcessingNotice({ message: 'Pose analysis could not be completed. Please review the error and try again.', error: true });
    } finally {
      setBusy(false);
      setAnalysisProgress(null);
    }
  }

  async function openSession(saved: SessionUploadResponse) {
    setSession(saved);
    setQuality(null);
    setTracking(null);
    setPose(null);
    setBowlerHistory(null);
    setWorkspaceError(null);
    setAnalysisProgress(null);
    setRoute('session-workspace');
    setBusy(true);

    try {
      const [qualityResult, trackingResult, historyResult] = await Promise.all([
        checkVideoQuality(saved.session_id).catch(() => null),
        getSubjectTracking(saved.session_id).catch(() => null),
        getBowlerProgress(saved.bowler_name).catch(() => null),
      ]);

      setQuality(qualityResult);
      setTracking(trackingResult);
      setBowlerHistory(historyResult);

      const integrityPassed = qualityResult?.metrics.some(
        (metric) =>
          metric.name === 'Video integrity' &&
          metric.status === 'reliable' &&
          metric.value?.opened === true,
      );

      if (integrityPassed && trackingResult?.confirmed_interval) {
        try {
          const savedAssessment = await getSavedPoseAssessment(saved.session_id);
          if (savedAssessment) {
            setPose(savedAssessment);
            setBowlerHistory(await getBowlerProgress(saved.bowler_name).catch(() => historyResult));
          } else {
            const assessment = await runBrowserAnalysis(saved.session_id);
            setPose(assessment);
            setBowlerHistory(await getBowlerProgress(saved.bowler_name).catch(() => historyResult));
          }
        } catch (analysisError) {
          console.error('Saved-session browser pose analysis failed:', analysisError);

          setWorkspaceError(
            analysisError instanceof Error
              ? analysisError.message
              : 'Pose review could not be loaded. Recheck the bowler selection and delivery interval, then try again.',
          );
        }
      }
    } finally {
      setBusy(false);
      setAnalysisProgress(null);
    }
  }

  async function analyzeCurrentSession() {
    if (!session) return;

    if (!tracking?.confirmed_interval) {
      setWorkflowStep(3);
      setError('Select and track the bowler, then confirm a delivery interval to continue.');
      setRoute('new-session');
      return;
    }

    await continueToAnalysis();
  }

  function resumeTracking() {
    if (!session) return;

    setWorkflowStep(3);
    setError(null);
    setRoute('new-session');
  }

  const labelClass = 'block text-sm font-medium text-text-primary';

  const inputClass = 'mt-2 min-h-12 w-full rounded-xl border border-surface-600 bg-surface-900 px-3 text-base text-text-primary outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-400/20';

  return (
    <AppNavigation route={route} navigate={navigate}>
      {route === 'dashboard' && (
        <DashboardPage
          sessions={sessions}
          onNavigate={navigate}
          onOpenSession={openSession}
        />
      )}

      {route === 'bowlers' && (
        <BowlersPage
          sessions={sessions}
          onOpenSession={openSession}
          onNewSession={() => navigate('new-session')}
        />
      )}

      {route === 'sessions' && (
        <div>
          {sessionsError && (
            <p role="alert" className="mx-auto mt-4 max-w-6xl rounded-xl bg-amber-950/30 p-3 text-sm text-accent-amber">
              {sessionsError}
            </p>
          )}

          {sessionsLoading ? (
            <p className="py-12 text-center text-text-secondary">
              Loading saved sessions…
            </p>
          ) : (
            <SessionsPage
              sessions={sessions}
              onOpenSession={openSession}
            />
          )}
        </div>
      )}

      {route === 'reports' && (
        <ReportsPage
          sessions={sessions}
          onOpenSession={openSession}
        />
      )}

      {route === 'session-workspace' && session && (
        <>
          <SessionWorkspacePage
            session={session}
            quality={quality}
            trackingConfirmed={Boolean(tracking?.confirmed_interval)}
            pose={pose}
            bowlerHistory={bowlerHistory}
            onOpenSession={openSession}
            loading={busy}
            error={workspaceError}
            onRunAnalysis={analyzeCurrentSession}
            onBack={() => navigate('sessions')}
            onReviewTracking={resumeTracking}
          />
        </>
      )}

      {route === 'new-session' && (
        <main className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
          <PageHeader
            eyebrow="New session"
            title={workflowStep <= 2 ? 'Create a bowling session' : session?.bowler_name ?? 'Review the bowler'}
            description={
              workflowStep <= 2
                ? 'A few simple steps to prepare a video for visual review.'
                : 'Select the bowler, review the tracked video, and confirm the delivery interval.'
            }
          />

          <WorkflowProgress current={workflowStep} />

          {workflowStep === 1 && (
            <form
              onSubmit={continueFromDetails}
              className="space-y-4 rounded-2xl border border-surface-700 bg-surface-800/60 p-4 sm:p-6"
            >
              <div>
                <h2 className="text-lg font-semibold">Session details</h2>
                <p className="mt-1 text-sm text-text-secondary">
                  Tell us about the bowler and camera view.
                </p>
              </div>

              <label className={labelClass}>
                Bowler
                <input
                  list="saved-bowlers"
                  required
                  maxLength={120}
                  value={bowlerName}
                  onChange={(event) => setBowlerName(event.target.value)}
                  placeholder="Select or enter bowler name"
                  autoComplete="off"
                  className={inputClass}
                />
                <datalist id="saved-bowlers">
                  {knownBowlers.map((name) => (
                    <option key={name} value={name} />
                  ))}
                </datalist>
              </label>

              <div className="grid gap-4 sm:grid-cols-2">
                <label className={labelClass}>
                  Session date
                  <input
                    type="date"
                    required
                    value={sessionDate}
                    onChange={(event) => setSessionDate(event.target.value)}
                    className={inputClass}
                  />
                </label>

                <label className={labelClass}>
                  Bowling style
                  <select
                    value={bowlingType}
                    onChange={(event) => setBowlingType(event.target.value as BowlingType)}
                    className={inputClass}
                  >
                    <option value="fast">Fast</option>
                    <option value="medium">Medium</option>
                    <option value="spin">Spin</option>
                  </select>
                </label>

                <label className={labelClass}>
                  Bowling arm
                  <select
                    value={bowlingArm}
                    onChange={(event) => setBowlingArm(event.target.value as BowlingArm)}
                    className={inputClass}
                  >
                    <option value="right">Right arm</option>
                    <option value="left">Left arm</option>
                  </select>
                </label>

                <label className={labelClass}>
                  Camera view
                  <select
                    value={cameraView}
                    onChange={(event) => setCameraView(event.target.value as CameraView)}
                    className={inputClass}
                  >
                    <option value="front">Front</option>
                    <option value="side">Side</option>
                    <option value="rear">Rear</option>
                    <option value="other">Other</option>
                  </select>
                </label>
              </div>

              <label className={labelClass}>
                Coach notes <span className="font-normal text-text-muted">(optional)</span>
                <textarea
                  rows={3}
                  maxLength={2000}
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  placeholder="Add context for this session"
                  className={`${inputClass} resize-y py-3`}
                />
              </label>

              {error && (
                <p role="alert" className="text-sm text-accent-red">
                  {error}
                </p>
              )}

              <div className="flex justify-end">
                <button
                  type="submit"
                  className="min-h-12 rounded-xl bg-brand-600 px-6 text-sm font-semibold"
                >
                  Continue to video
                </button>
              </div>
            </form>
          )}

          {workflowStep === 2 && (
            <form
              onSubmit={uploadAndContinue}
              className="space-y-4 rounded-2xl border border-surface-700 bg-surface-800/60 p-4 sm:p-6"
            >
              <div>
                <h2 className="text-lg font-semibold">Upload bowling video</h2>
                <p className="mt-1 text-sm text-text-secondary">
                  Choose an MP4 or MOV video, up to 200 MB.
                </p>
              </div>

              {previewUrl ? (
                <div className="space-y-3">
                  <video
                    src={previewUrl}
                    controls
                    playsInline
                    className="max-h-[60vh] w-full rounded-xl bg-black object-contain"
                  />

                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-surface-900 p-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{video?.name}</p>
                      <p className="text-xs text-text-muted">
                        {video ? `${(video.size / 1024 / 1024).toFixed(1)} MB` : ''}
                      </p>
                    </div>

                    <label className="inline-flex min-h-10 cursor-pointer items-center rounded-lg border border-surface-600 px-3 text-sm">
                      Replace video
                      <input
                        type="file"
                        accept=".mp4,.mov,video/mp4,video/quicktime"
                        onChange={chooseVideo}
                        className="sr-only"
                      />
                    </label>
                  </div>
                </div>
              ) : (
                <label className="flex min-h-48 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-surface-600 bg-surface-900/60 p-6 text-center hover:border-brand-400">
                  <span className="text-lg font-medium">Choose a video</span>
                  <span className="mt-2 text-sm text-text-secondary">
                    Select a bowling video from this device
                  </span>
                  <input
                    type="file"
                    accept=".mp4,.mov,video/mp4,video/quicktime"
                    onChange={chooseVideo}
                    className="sr-only"
                  />
                </label>
              )}

              {error && (
                <p role="alert" className="text-sm text-accent-red">
                  {error}
                </p>
              )}

              {busy && (
                <div role="status" className="space-y-2">
                  <div className="flex justify-between text-sm text-text-secondary">
                    <span>Uploading video…</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <progress
                    value={uploadProgress}
                    max="100"
                    className="h-2 w-full accent-brand-500"
                  />
                </div>
              )}

              <div className="flex flex-wrap justify-between gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    setWorkflowStep(1);
                  }}
                  className="min-h-11 rounded-xl border border-surface-600 px-4 text-sm"
                >
                  Back
                </button>

                <button
                  type="submit"
                  disabled={!video || busy || !health}
                  className="min-h-12 rounded-xl bg-brand-600 px-6 text-sm font-semibold disabled:opacity-40"
                >
                  {busy ? 'Uploading…' : 'Upload and continue'}
                </button>
              </div>

              {!health && (
                <p className="text-sm text-accent-amber">
                  Session service is currently unavailable.
                </p>
              )}
            </form>
          )}

          {workflowStep >= 3 && session && (
            <>
              <VideoWorkspace
                key={workflowStep}
                session={session}
                tracking={tracking}
                stage={
                  workflowStep === 3
                    ? 'select'
                    : workflowStep === 4
                      ? 'tracking'
                      : 'review'
                }
                busy={busy}
                error={error}
                onTrack={runTracking}
                onConfirm={confirmInterval}
                onRedraw={redrawSelection}
                onContinue={() =>
                  workflowStep === 4
                    ? setWorkflowStep(5)
                    : void continueToAnalysis()
                }
              />

              <div className="mt-4 flex justify-between">
                <button
                  type="button"
                  onClick={() =>
                    workflowStep === 3
                      ? setWorkflowStep(2)
                      : workflowStep === 4
                        ? setWorkflowStep(3)
                        : setWorkflowStep(4)
                  }
                  className="min-h-10 text-sm text-text-secondary"
                >
                  ← Back
                </button>

                <span className="self-center text-xs text-text-muted">
                  Session with {session.bowler_name}
                </span>
              </div>
            </>
          )}
        </main>
      )}

      {(processingNotice || (analysisProgress && busy)) && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/65 px-4 backdrop-blur-sm" role="presentation">
          <section role="status" aria-live="polite" className="w-full max-w-sm rounded-2xl border border-surface-600 bg-surface-800 p-6 text-center shadow-2xl">
            {processingNotice?.done ? (
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-brand-500/15 text-2xl text-brand-300">✓</div>
            ) : processingNotice?.error ? (
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-amber-500/15 text-2xl text-amber-300">!</div>
            ) : (
              <div className="mx-auto mb-4 h-11 w-11 animate-spin rounded-full border-4 border-surface-600 border-t-brand-400" />
            )}
            <h2 className="text-lg font-semibold text-text-primary">
              {processingNotice?.done ? 'All done!' : processingNotice?.error ? 'Needs another try' : 'Processing'}
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">{analysisProgress ?? processingNotice?.message}</p>
            {!processingNotice?.done && !processingNotice?.error && <p className="mt-4 text-xs text-text-muted">Please keep this page open while the analysis runs.</p>}
          </section>
        </div>
      )}
    </AppNavigation>
  );
}

export default App;
