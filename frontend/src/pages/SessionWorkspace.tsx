import { Component, useEffect, useState, type ErrorInfo, type ReactNode } from 'react';
import { PageHeader } from '../components/AppNavigation';
import { sessionVideoUrl } from '../services/api';
import { coachFrameStatus, coachRegionEvidence, coachRegionStatus } from '../presentation/posePresentation';
import { buildCoachingInsights, frameStageLabel } from '../presentation/coachingInsights';
import type { PoseFrame, BowlerProgressResponse, SessionUploadResponse } from '../types';
import type { PoseAssessment, QualityAssessment } from '../types';

type WorkspaceTab = 'overview' | 'deliveries' | 'pose' | 'comparison' | 'report';

export function SessionWorkspacePage({ session, quality, trackingConfirmed, pose, bowlerHistory, onOpenSession, loading, error, onRunAnalysis, onBack, onReviewTracking }: {
  session: SessionUploadResponse;
  quality: QualityAssessment | null;
  trackingConfirmed: boolean;
  pose: PoseAssessment | null;
  bowlerHistory: BowlerProgressResponse | null;
  onOpenSession: (session: SessionUploadResponse) => void;
  loading: boolean;
  error: string | null;
  onRunAnalysis: () => void;
  onBack: () => void;
  onReviewTracking: () => void;
}) {
  const [tab, setTab] = useState<WorkspaceTab>('overview');
  const tabs: { id: WorkspaceTab; label: string; available: boolean }[] = [
    { id: 'overview', label: 'Overview', available: true },
    { id: 'deliveries', label: 'Deliveries', available: true },
    { id: 'pose', label: 'Pose analysis', available: true },
    { id: 'comparison', label: 'Comparison', available: true },
    { id: 'report', label: 'Report', available: true },
  ];
  const qualityLabel = quality?.overall_assessment === 'suitable' ? 'Ready for analysis' : quality?.overall_assessment === 'suitable_with_limitations' ? 'Analysis available with limitations' : quality ? 'Unable to analyse this recording' : 'Recording review not run';
  return <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
    <button type="button" onClick={onBack} className="mb-4 min-h-10 text-sm font-medium text-text-secondary hover:text-text-primary">← Back to sessions</button>
    <PageHeader eyebrow="Session workspace" title={session.bowler_name} description={`${session.session_date} · ${session.bowling_type} · ${session.bowling_arm} arm · ${session.camera_view} camera view`} />
    <div className="mb-5 flex gap-1 overflow-x-auto rounded-xl border border-surface-700 bg-surface-800/60 p-1" role="tablist" aria-label="Session workspace">{tabs.map((item) => <button key={item.id} role="tab" aria-selected={tab === item.id} disabled={!item.available} title={!item.available ? `${item.label} is not available yet` : undefined} onClick={() => item.available && setTab(item.id)} className={`min-h-11 shrink-0 rounded-lg px-4 text-sm font-medium ${!item.available ? 'cursor-not-allowed text-text-muted opacity-50' : tab === item.id ? 'bg-brand-600 text-white' : 'text-text-secondary hover:bg-surface-700'}`}>{item.label}{!item.available && <span className="ml-1 text-[10px]">Soon</span>}</button>)}</div>

    <WorkspaceTabBoundary key={tab}>
    {tab === 'overview' && <div className="grid gap-5 lg:grid-cols-[minmax(0,1.25fr)_minmax(280px,.75fr)]"><section className="overflow-hidden rounded-2xl border border-surface-700 bg-black"><video src={sessionVideoUrl(session.session_id)} controls playsInline preload="metadata" className="max-h-[65vh] w-full bg-black object-contain"/><div className="bg-surface-800 p-4"><h2 className="font-semibold">Session recording</h2><p className="mt-1 text-sm text-text-secondary">Bowling action video for {session.bowler_name}.</p></div></section><aside className="space-y-3"><article className="rounded-2xl border border-surface-700 bg-surface-800/60 p-5"><p className="text-xs uppercase tracking-wide text-text-muted">Recording status</p><h2 className="mt-2 font-semibold">{qualityLabel}</h2>{quality && <p className="mt-2 text-sm leading-relaxed text-text-secondary">{quality.overall_assessment === 'suitable' ? 'Initial recording checks passed. Bowler visibility is reviewed separately.' : quality.overall_assessment === 'suitable_with_limitations' ? 'Some recording checks were limited. Review the video as you continue.' : 'The recording check found an issue that may prevent useful analysis.'}</p>}{!quality && <p className="mt-2 text-sm text-text-secondary">Recording review is not available for this saved session yet.</p>}</article><article className="rounded-2xl border border-surface-700 bg-surface-800/60 p-5"><p className="text-xs uppercase tracking-wide text-text-muted">Bowler selection</p><h2 className="mt-2 font-semibold">{trackingConfirmed ? 'Interval confirmed' : 'Needs review'}</h2><p className="mt-2 text-sm text-text-secondary">{trackingConfirmed ? 'A delivery interval is saved for this session.' : 'Select and track the bowler, then confirm a delivery interval.'}</p></article><article className="rounded-2xl border border-surface-700 bg-surface-800/60 p-5"><p className="text-xs uppercase tracking-wide text-text-muted">Movement review</p><h2 className="mt-2 font-semibold">{pose ? `${pose.detected_frame_count} sampled moments with pose` : 'Not completed'}</h2><p className="mt-2 text-sm text-text-secondary">{pose ? pose.pose_validation_status === 'valid' ? 'Body landmarks were detected clearly in sampled moments.' : 'Some movements need visual review or could not be assessed.' : 'Pose results appear here after the review is run.'}</p></article><button type="button" onClick={onRunAnalysis} disabled={loading} className="min-h-12 w-full rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white disabled:opacity-50">{loading ? 'Reviewing session…' : pose ? 'Refresh available results' : 'Continue to analysis'}</button><button type="button" onClick={onReviewTracking} className="min-h-11 w-full rounded-xl border border-surface-600 px-4 text-sm">{trackingConfirmed ? 'Review bowler selection' : 'Select and track the bowler'}</button>{error && <p role="alert" className="rounded-xl border border-accent-amber/30 bg-amber-950/20 p-3 text-sm text-accent-amber">{error}</p>}</aside></div>}

    {tab === 'deliveries' && <DeliveriesPanel pose={pose} session={session} history={bowlerHistory} onOpenSession={onOpenSession} />}
    {tab === 'comparison' && <ComparisonPanel pose={pose} history={bowlerHistory} currentSession={session} />}
    {tab === 'pose' && <PosePanel pose={pose} session={session} loading={loading} onRunAnalysis={onRunAnalysis} error={error} />}
    {tab === 'report' && <ReportPanel session={session} quality={quality} pose={pose} />}
    </WorkspaceTabBoundary>
  </main>;
}

function PosePanel({ pose, session, loading, onRunAnalysis, error }: { pose: PoseAssessment | null; session: SessionUploadResponse; loading: boolean; onRunAnalysis: () => void; error: string | null }) {
  const [lightbox, setLightbox] = useState<{ src: string; title: string } | null>(null);
  if (!pose) return <div className="rounded-2xl border border-surface-700 bg-surface-800/60 p-6"><h2 className="text-lg font-semibold">Pose analysis</h2><p className="mt-2 text-sm text-text-secondary">Pose overlays are shown after the bowler is tracked and a delivery interval is confirmed.</p><button type="button" onClick={onRunAnalysis} disabled={loading} className="mt-4 min-h-11 rounded-xl bg-brand-600 px-4 text-sm font-semibold disabled:opacity-50">{loading ? 'Reviewing…' : 'Run pose analysis'}</button>{error && <p className="mt-3 text-sm text-accent-amber">{error}</p>}</div>;
  const summary = pose.pose_validation_status === 'valid' ? 'Body landmarks were detected clearly in sampled moments.' : pose.pose_validation_status === 'invalid' ? 'Some predicted landmarks need visual review.' : pose.detected_frame_count ? 'Some body movements are unclear or could not be checked.' : 'There was not enough visual evidence to assess body landmarks.';
  const labels: Record<string, string> = { head: 'Head', upper_body: 'Upper body', arms: 'Arms', lower_body: 'Lower body' };
  const toneClasses = { green: 'border-brand-500/40 bg-brand-950/20 text-brand-300', amber: 'border-accent-amber/40 bg-amber-950/20 text-accent-amber', red: 'border-accent-red/40 bg-red-950/20 text-red-200', muted: 'border-surface-600 bg-surface-900 text-text-secondary' };
  return <div className="space-y-5">
    <section className="rounded-2xl border border-surface-700 bg-surface-800/60 p-5"><h2 className="text-lg font-semibold">Pose analysis</h2><p className="mt-2 text-sm leading-relaxed text-text-secondary">{summary} The model detects landmarks; the coaching interpretation below translates measurable evidence into cautious, practical guidance.</p><p className="mt-2 text-sm text-text-muted">Pose detected in {pose.detected_frame_count} of {pose.sampled_frame_count} sampled moments.</p></section>
    {pose.biomechanics && <section className="rounded-2xl border border-surface-700 bg-surface-800/60 p-5 space-y-4"><div><h2 className="text-lg font-semibold">Front-view biomechanics</h2><p className="mt-1 text-sm text-text-secondary">End-on camera · 2D image-plane measurements. Values are estimates and require coach interpretation.</p></div><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(pose.biomechanics.summary).map(([key, value]) => <article key={key} className="rounded-xl border border-surface-700 bg-surface-900 p-3"><p className="text-xs capitalize text-text-muted">{key.replaceAll('_',' ')}</p><p className="mt-1 text-xl font-semibold">{value.median === null ? 'Unavailable' : `${value.median}${key.includes('ratio') ? '' : '°'}`}</p><p className="mt-1 text-xs text-text-secondary">{value.valid_frames}/{value.sampled_frames} measurable frames</p></article>)}</div>{pose.biomechanics.observations.map((item, index) => <article key={index} className="rounded-xl bg-surface-900 p-3"><h3 className="font-medium">{item.title}</h3><p className="mt-1 text-sm text-text-secondary">{item.finding}</p><p className="mt-2 text-xs text-text-muted">Coach review: {item.coach_action}</p><p className="mt-1 text-xs text-text-muted">{item.caveat}</p></article>)}<div className="rounded-xl border border-accent-amber/30 bg-amber-950/10 p-3"><h3 className="font-medium">Interpretation limitations</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-text-secondary">{pose.biomechanics.scientific_limitations.map((item,index)=><li key={index}>{item}</li>)}</ul></div></section>}
    {pose.biomechanics && <CoachingInferencePanel pose={pose} bowlingArm={session.bowling_arm} />}
    <section aria-label="Body region evidence" className="grid gap-3 sm:grid-cols-2">{pose.regions.map((region) => {
      const status = coachRegionStatus(region, pose.validation_schema_version);
      const evidence = coachRegionEvidence(region);
      return <article key={region.name} className="min-w-0 rounded-2xl border border-surface-700 bg-surface-800/60 p-4">
        <div className="flex flex-wrap items-start justify-between gap-2"><h3 className="font-semibold">{labels[region.name] ?? 'Body region'}</h3><span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${toneClasses[status.tone]}`}>{status.label}</span></div>
        <p className="mt-3 text-sm text-text-secondary">Landmarks detected: {evidence.detected.count} of {evidence.detected.total} moments.</p>
        <p className="mt-1 text-sm text-text-secondary">Enough evidence for checks: {evidence.sufficient.count} of {evidence.sufficient.total} moments.</p>
        <p className="mt-1 text-sm text-text-secondary">Checks passed: {evidence.validated.count} of {evidence.validated.total} moments.</p>
        {(region.insufficient_evidence_frames > 0 || region.failed_frames > 0 || status.tone === 'muted' || status.tone === 'amber' || status.tone === 'red') && <p className="mt-3 text-sm leading-relaxed text-text-secondary">{region.failed_frames > 0 ? `${region.failed_frames} moment(s) had landmarks flagged by checks. ` : ''}{region.insufficient_evidence_frames > 0 ? `${region.insufficient_evidence_frames} moment(s) had insufficient evidence. ` : ''}{status.explanation}</p>}
      </article>;
    })}</section>
    <section className="space-y-3" aria-label="Sampled pose frames"><div><h2 className="text-lg font-semibold">Sampled moments</h2><p className="mt-1 text-sm text-text-secondary">Each frame includes the original image and the detected pose overlay. Uncertain moments remain visible for review.</p></div>
      <div className="grid gap-4 xl:grid-cols-2">{pose.frames.map((frame) => <article key={frame.frame_number} className="overflow-hidden rounded-2xl border border-surface-700 bg-surface-800/60">
        <div className="grid grid-cols-1 gap-px bg-surface-700 sm:grid-cols-2"><figure className="min-w-0 bg-black"><button type="button" onClick={() => setLightbox({ src: frame.original_image_url, title: `Original frame · ${frame.timestamp_seconds?.toFixed(2) ?? frame.frame_number} seconds` })} className="block w-full cursor-zoom-in" aria-label="Open original frame"><img loading="lazy" src={frame.original_image_url} alt={`Original video frame at ${frame.timestamp_seconds?.toFixed(1) ?? 'unknown'} seconds`} className="aspect-video w-full bg-black object-contain"/></button><figcaption className="px-3 py-2 text-xs text-text-muted">Original frame · click to enlarge</figcaption></figure><figure className="min-w-0 bg-black"><button type="button" onClick={() => setLightbox({ src: frame.overlay_image_url, title: `Pose overlay · ${frame.timestamp_seconds?.toFixed(2) ?? frame.frame_number} seconds` })} className="block w-full cursor-zoom-in" aria-label="Open pose overlay"><img loading="lazy" src={frame.overlay_image_url} alt={`Pose overlay at ${frame.timestamp_seconds?.toFixed(1) ?? 'unknown'} seconds`} className="aspect-video w-full bg-black object-contain"/></button><figcaption className="px-3 py-2 text-xs text-text-muted">Pose overlay · click to enlarge</figcaption></figure></div>
        <div className="p-4"><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-base font-semibold">{frame.timestamp_seconds === null ? `Frame ${frame.frame_number}` : `${frame.timestamp_seconds.toFixed(2)} seconds`}</h3><span className={`rounded-full px-2.5 py-1 text-xs font-medium ${frame.validation_outcome === 'validated' ? 'bg-brand-500/10 text-brand-300' : frame.validation_outcome === 'validation_failed' ? 'bg-red-950/30 text-red-200' : 'bg-amber-950/30 text-accent-amber'}`}>{frame.detected ? 'Pose detected' : 'Pose unclear'}</span></div><p className="mt-2 text-sm leading-relaxed text-text-secondary">{coachFrameStatus(frame.validation_outcome, frame.detected)}</p></div>
      </article>)}</div>
    </section>
    {lightbox && <div role="dialog" aria-modal="true" aria-label={lightbox.title} onClick={() => setLightbox(null)} className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4"><div className="w-full max-w-6xl" onClick={(event) => event.stopPropagation()}><div className="mb-3 flex items-center justify-between gap-3"><p className="text-sm font-medium text-white">{lightbox.title}</p><button type="button" autoFocus onClick={() => setLightbox(null)} className="rounded-lg bg-white/10 px-4 py-2 text-sm text-white hover:bg-white/20">Close ✕</button></div><img src={lightbox.src} alt={lightbox.title} className="max-h-[82vh] w-full rounded-xl bg-black object-contain"/></div></div>}
    <video src={sessionVideoUrl(session.session_id)} controls playsInline preload="metadata" className="max-h-[65vh] w-full rounded-2xl bg-black object-contain"/>
  </div>;
}


function CoachingInferencePanel({ pose, bowlingArm }: { pose: PoseAssessment; bowlingArm: 'left' | 'right' }) {
  const insights = pose.biomechanics ? buildCoachingInsights(pose.biomechanics, bowlingArm) : [];
  const [selectedIndex, setSelectedIndex] = useState(0);
  const selectedFrame = pose.frames[Math.min(selectedIndex, Math.max(0, pose.frames.length - 1))];
  const selectedMeasurements = pose.biomechanics?.frames.find((item) => item.frame_number === selectedFrame?.frame_number)?.measurements ?? {};
  const styles = {
    positive: 'border-emerald-500/30 bg-emerald-950/20 text-emerald-300',
    review: 'border-amber-500/30 bg-amber-950/20 text-amber-300',
    limited: 'border-surface-600 bg-surface-900 text-text-secondary',
  };
  return <section className="space-y-5 rounded-2xl border border-brand-500/30 bg-surface-800/60 p-5">
    <div><h2 className="text-xl font-semibold">Your beginner-friendly bowling coach</h2><p className="mt-1 text-sm text-text-secondary">This report uses your detected body points and measured 2D movement. It explains what the video can show, what to review and why it may matter.</p></div>
    <div className="grid gap-3 sm:grid-cols-3">
      <article className="rounded-xl bg-surface-900 p-3"><p className="text-xs text-text-muted">Camera setup</p><p className="mt-1 font-semibold">Fixed end-on view</p><p className="mt-1 text-xs text-text-secondary">Feedback is designed for this same view.</p></article>
      <article className="rounded-xl bg-surface-900 p-3"><p className="text-xs text-text-muted">Evidence used</p><p className="mt-1 font-semibold">{pose.biomechanics?.frames.length ?? 0} sampled moments</p><p className="mt-1 text-xs text-text-secondary">Only landmarks that pass the measurement checks are used for angles. Other visible points remain available for visual review.</p></article>
      <article className="rounded-xl bg-surface-900 p-3"><p className="text-xs text-text-muted">How to read this</p><p className="mt-1 font-semibold">Review cues, not grades</p><p className="mt-1 text-xs text-text-secondary">The app does not label a bowler good or bad.</p></article>
    </div>
    <div className="space-y-3">
      <div><h3 className="text-lg font-semibold">What you are doing well and what to review</h3><p className="mt-1 text-sm text-text-secondary">Green means the measured line stayed fairly consistent in this clip. Amber means review the movement in the video. Grey means the evidence is not enough to judge.</p></div>
      {insights.length ? insights.map((item) => <article key={item.id} className="rounded-xl border border-surface-700 bg-surface-900 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-semibold">{item.title}</h4><span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${styles[item.status]}`}>{item.status === 'positive' ? 'Good consistency' : item.status === 'review' ? 'Worth reviewing' : 'Limited evidence'}</span></div>
        <p className="mt-3 text-sm leading-relaxed text-text-secondary"><strong className="text-text-primary">What we measured:</strong> {item.observation}</p>
        <p className="mt-2 text-sm leading-relaxed text-text-secondary"><strong className="text-text-primary">What to try:</strong> {item.tryNext}</p>
        <p className="mt-2 text-sm leading-relaxed text-text-secondary"><strong className="text-text-primary">Coach's cue:</strong> {item.coachCue}</p>
        <p className="mt-2 text-sm leading-relaxed text-text-secondary"><strong className="text-text-primary">Why it may help:</strong> {item.benefit}</p>
        <p className="mt-2 text-xs text-text-muted">Evidence: {item.evidence}</p>
      </article>) : <p className="rounded-xl bg-surface-900 p-4 text-sm text-text-secondary">No biomechanics measurements are available yet. The app will not guess what the bowler should change.</p>}
    </div>
    <div className="space-y-3">
      <div><h3 className="text-lg font-semibold">What a coach would check at each moment</h3><p className="mt-1 text-sm text-text-secondary">Select any sampled frame. The coaching checklist reads the measurements for that exact moment and explains what to watch in plain English. Earlier, middle and later labels are only positions in the clip, not automatically detected bowling phases.</p></div>
      {pose.frames.length > 0 && <>
        <div className="flex flex-wrap gap-2">{pose.frames.map((item, index) => <button key={item.frame_number} type="button" onClick={() => setSelectedIndex(index)} aria-pressed={selectedIndex === index} className={`rounded-lg border px-3 py-2 text-xs ${selectedIndex === index ? 'border-brand-500 bg-brand-600 text-white' : 'border-surface-600 bg-surface-900 text-text-secondary'}`}>{item.timestamp_seconds === null ? `Frame ${item.frame_number}` : `${item.timestamp_seconds.toFixed(2)} s`}</button>)}</div>
        {selectedFrame && <div className="grid gap-3 md:grid-cols-2"><CoachMomentGuide frame={selectedFrame} index={selectedIndex} total={pose.frames.length} measurements={selectedMeasurements} bowlingArm={bowlingArm} /><DetectedPoseGuide frame={selectedFrame} index={selectedIndex} total={pose.frames.length} /></div>}
        {selectedFrame && <article className="rounded-xl border border-surface-700 bg-surface-900 p-4"><h4 className="font-semibold">Alignment measurements at this exact moment</h4><p className="mt-1 text-xs text-text-muted">These values change when you select a different frame. They are projected 2D measurements, not ideal target angles.</p><div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">{[['Shoulder tilt','shoulder_line_tilt'],['Hip tilt','hip_line_tilt'],['Left elbow','left_elbow_angle'],['Right elbow','right_elbow_angle']].map(([label,key])=>{const value=selectedMeasurements[key]?.value;return <div key={key} className="rounded-lg bg-surface-800 p-3"><p className="text-xs text-text-muted">{label}</p><p className="mt-1 font-semibold">{value===null||value===undefined?'Unavailable':`${value.toFixed(1)}°`}</p></div>;})}</div></article>}
      </>}
      <div className="rounded-xl border border-surface-700 bg-surface-900 p-4"><h4 className="font-semibold">How to practise from this review</h4><ol className="mt-2 list-decimal space-y-2 pl-5 text-sm text-text-secondary"><li>Choose a frame where a measurement changes noticeably and open its original image.</li><li>Watch the two or three frames before and after it. A bowling action is continuous; one still image is never the whole story.</li><li>Practise the suggested movement slowly without a ball, then repeat at a comfortable pace.</li><li>Compare the next recording from the same camera position. Look for a more repeatable action and confirm changes with a coach.</li></ol></div>
    </div>
    <section className="space-y-3 rounded-xl border border-surface-700 bg-surface-900 p-4">
      <div><h3 className="text-lg font-semibold">Your practice priorities</h3><p className="mt-1 text-sm text-text-secondary">These are selected from this video's own measurements, not a generic checklist.</p></div>
      {[...insights].filter((item) => item.status === 'review').concat(insights.filter((item) => item.status === 'limited')).slice(0, 3).map((item, index) => <article key={item.id} className="rounded-lg bg-surface-800 p-3"><p className="text-xs font-semibold uppercase tracking-wide text-text-muted">Focus {index + 1} · {item.title}</p><p className="mt-1 text-sm font-medium">{item.coachCue}</p><p className="mt-1 text-sm text-text-secondary">{item.tryNext}</p></article>)}
      {insights.length > 0 && insights.every((item) => item.status === 'positive') && <p className="text-sm text-text-secondary">No major consistency issue was flagged by the available measurements. Keep the action comfortable and repeatable, then compare the next recording.</p>}
      {!insights.length && <p className="text-sm text-text-secondary">There are not enough reliable landmarks to suggest a practice priority. Review the original video with a coach.</p>}
    </section>
    <div className="rounded-xl border border-amber-500/30 bg-amber-950/10 p-4"><h3 className="font-semibold">What this camera cannot tell us</h3><p className="mt-1 text-sm text-text-secondary">This view cannot reliably measure depth, trunk rotation, true 3D joint angles, ball release, ball speed, target accuracy or bowling legality. Angle ranges shown here are 2D measurements, not ideal targets. Use the feedback as a learning aid and confirm technique changes with a qualified cricket coach.</p></div>
  </section>;
}

const SKELETON_CONNECTIONS: [string, string][] = [
  ['left_shoulder','right_shoulder'], ['left_shoulder','left_elbow'], ['left_elbow','left_wrist'],
  ['right_shoulder','right_elbow'], ['right_elbow','right_wrist'], ['left_shoulder','left_hip'],
  ['right_shoulder','right_hip'], ['left_hip','right_hip'], ['left_hip','left_knee'],
  ['left_knee','left_ankle'], ['right_hip','right_knee'], ['right_knee','right_ankle'],
];

class WorkspaceTabBoundary extends Component<{ children: ReactNode }, { hasError: boolean; message: string }> {
  state = { hasError: false, message: '' };
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, message: error.message || 'An unexpected display error occurred.' };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Session workspace tab failed to render:', error, info.componentStack);
  }
  render() {
    if (this.state.hasError) return <section role="alert" className="rounded-2xl border border-amber-500/40 bg-amber-950/20 p-5">
      <h2 className="font-semibold">This section could not be displayed</h2>
      <p className="mt-2 text-sm text-text-secondary">The session and saved video are still available. A display error occurred: {this.state.message}</p>
      <p className="mt-2 text-xs text-text-muted">Try another tab or reload the page. This message helps identify the exact problem instead of showing a blank screen.</p>
    </section>;
    return this.props.children;
  }
}

function historyDate(value?: string) {
  if (!value) return 'Date unavailable';
  const parsed = new Date(`${value.slice(0, 10)}T12:00:00`);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

function movementStage(index: number, total: number) {
  if (total <= 1 || index / (total - 1) < 0.34) return 'Earlier movement';
  if (index / (total - 1) < 0.67) return 'Middle movement';
  return 'Later movement';
}

function CoachMomentGuide({ frame, index, total, measurements, bowlingArm }: {
  frame: PoseFrame;
  index: number;
  total: number;
  measurements: Record<string, { value: number | null; unit: string; confidence: number | null; status: string; interpretation: string }>;
  bowlingArm: 'left' | 'right';
}) {
  const stage = frameStageLabel(index, total);
  const value = (key: string) => measurements[key]?.value ?? null;
  const shoulder = value('shoulder_line_tilt');
  const hip = value('hip_line_tilt');
  const bowlingElbow = value(`${bowlingArm}_elbow_angle`);
  const supportSide = bowlingArm === 'right' ? 'left' : 'right';
  const supportElbow = value(`${supportSide}_elbow_angle`);
  const cues = [
    {
      title: 'Upper body',
      measured: shoulder === null ? 'Not clear in this frame' : `${Math.abs(shoulder).toFixed(1)}° shoulder-line tilt`,
      cue: shoulder === null ? 'Keep both shoulders visible; review the original frame.' : Math.abs(shoulder) > 15 ? 'Check whether the head and chest are falling sideways. Allow natural shoulder turn; do not force the shoulders flat.' : 'The shoulder line looks relatively level in this frame. Keep the same relaxed head and chest control as you move.',
    },
    {
      title: 'Hip and base',
      measured: hip === null ? 'Not clear in this frame' : `${Math.abs(hip).toFixed(1)}° hip-line tilt`,
      cue: hip === null ? 'Review the original frame; both hip points are needed.' : Math.abs(hip) > 15 ? 'Check whether the trunk is dropping to one side. Support your body over your legs, while allowing the hips to turn naturally.' : 'The hip line is relatively level in this frame. Keep the stride controlled; do not lock the hips to preserve this angle.',
    },
    {
      title: 'Bowling arm',
      measured: bowlingElbow === null ? 'Elbow angle unavailable' : `${bowlingElbow.toFixed(1)}° projected elbow angle`,
      cue: bowlingElbow === null ? 'The bowling elbow or wrist is not clear enough to measure here.' : 'This is one instant in a moving action, not a target angle. Review the frames before and after it for a smooth, repeatable arm path. Never force the elbow to match a number.',
    },
    {
      title: 'Support arm',
      measured: supportElbow === null ? 'Not enough landmarks' : `${supportElbow.toFixed(1)}° projected elbow angle`,
      cue: supportElbow === null ? 'The other arm is not clear enough to assess in this moment.' : 'Check that the non-bowling arm helps your balance and timing, then comes through naturally. Avoid a loose, uncontrolled swing.',
    },
  ];
  return <article className="rounded-xl border border-surface-700 bg-surface-900 p-3">
    <h4 className="font-semibold">Coach's checklist for this moment</h4>
    <p className="text-xs text-text-muted">{stage} · {frame.timestamp_seconds === null ? `Frame ${frame.frame_number}` : `${frame.timestamp_seconds.toFixed(2)} s`} · {bowlingArm}-arm bowler</p>
    <div className="mt-3 space-y-3">{cues.map((cue) => <div key={cue.title} className="border-l-2 border-amber-400 pl-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2"><p className="text-sm font-semibold">{cue.title}</p><p className="text-xs text-text-muted">{cue.measured}</p></div>
      <p className="mt-1 text-sm leading-relaxed text-text-secondary">{cue.cue}</p>
    </div>)}</div>
    <div className="mt-3 rounded-lg bg-surface-800 p-3"><p className="text-xs font-semibold text-text-primary">What this means</p><p className="mt-1 text-xs leading-relaxed text-text-secondary">This is a selected video moment, not an automatically detected cricket phase. The cues are based on the visible 2D landmarks; compare several moments and the original video before changing technique.</p></div>
  </article>;
}

function DetectedPoseGuide({ frame, index, total }: { frame: PoseFrame; index: number; total: number }) {
  const visiblePoints = frame.keypoints.filter((point) =>
    point.coordinate_valid && point.x !== null && point.y !== null
    && (point.confidence ?? 0) >= 0.15,
  );
  const points = new Map(visiblePoints
    .map((point)=>[point.name,[point.x as number,point.y as number] as [number,number]]));
  const coords=[...points.values()];
  const xs=coords.map(([x])=>x), ys=coords.map(([,y])=>y);
  const minX=xs.length?Math.min(...xs):0, maxX=xs.length?Math.max(...xs):1;
  const minY=ys.length?Math.min(...ys):0, maxY=ys.length?Math.max(...ys):1;
  const spanX=Math.max(0.015,maxX-minX), spanY=Math.max(0.015,maxY-minY);
  const fitScale=Math.min(84/spanX,84/spanY);
  const centerX=(minX+maxX)/2, centerY=(minY+maxY)/2;
  const project=(x:number,y:number):[number,number]=>[50+(x-centerX)*fitScale,50+(y-centerY)*fitScale];
  const head=points.get('nose') ?? points.get('left_eye') ?? points.get('right_eye');
  return <article className="rounded-xl border border-surface-700 bg-surface-900 p-3">
    <h4 className="font-semibold">Your detected pose</h4>
    <p className="text-xs text-text-muted">{movementStage(index,total)} · {frame.timestamp_seconds===null?`Frame ${frame.frame_number}`:`${frame.timestamp_seconds.toFixed(2)} seconds`} · {frame.detected?'pose detected':'unclear pose'}</p>
    <svg viewBox="0 0 100 100" role="img" aria-label="Auto-framed detected pose skeleton from selected video frame" className="mt-2 h-64 w-full rounded-lg bg-black">
      {SKELETON_CONNECTIONS.map(([a,b])=>{const p1=points.get(a),p2=points.get(b);if(!p1||!p2)return null;const [x1,y1]=project(...p1),[x2,y2]=project(...p2);return <line key={a+b} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#38bdf8" strokeWidth="2.2" strokeLinecap="round"/>;})}
      {head&&(()=>{const [x,y]=project(...head);return <circle cx={x} cy={y} r="4.3" fill="none" stroke="#38bdf8" strokeWidth="1.8"/>;})()}
      {([['left_shoulder','right_shoulder'],['left_hip','right_hip']] as [string,string][]).map(([left,right])=>{const a=points.get(left),b=points.get(right);if(!a||!b)return null;const [x1,y1]=project(...a),[x2,y2]=project(...b);const y=(y1+y2)/2;return <g key={left}><line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#f59e0b" strokeWidth="2.4"/><line x1={Math.max(5,Math.min(x1,x2)-10)} y1={y} x2={Math.min(95,Math.max(x1,x2)+10)} y2={y} stroke="#f59e0b" strokeDasharray="2 2" strokeWidth=".8" opacity=".75"/></g>;})}
      {[...points.entries()].map(([name,[x,y]])=>{const [px,py]=project(x,y);return <circle key={name} cx={px} cy={py} r="2.6" fill="#fbbf24"><title>{name}</title></circle>;})}
      {points.size===0&&<text x="50" y="50" textAnchor="middle" fill="white" fontSize="5">Not enough validated landmarks</text>}
    </svg>
    <p className="mt-2 text-xs text-text-secondary">{points.size} detected landmarks shown, including provisional points that did not pass every validation check. They are useful for visual review but are not all used for measurements. The skeleton is zoomed and centred to the visible body.</p>
  </article>;
}

function DeliveriesPanel({
  pose, session, history, onOpenSession,
}: {
  pose: PoseAssessment | null;
  session: SessionUploadResponse;
  history: BowlerProgressResponse | null;
  onOpenSession: (session: SessionUploadResponse) => void;
}) {
  const entries = Array.isArray(history?.sessions) ? history.sessions.filter((item) => item?.session?.session_id) : [];
  const ordered = [...entries].sort((a, b) =>
    (a.session.session_date ?? '').localeCompare(b.session.session_date ?? '')
    || (a.session.created_at ?? '').localeCompare(b.session.created_at ?? ''),
  );
  const currentInterval = pose?.tracking?.confirmed_interval;
  return <section className="space-y-5">
    <div>
      <h2 className="text-lg font-semibold">Bowling video history</h2>
      <p className="mt-1 text-sm text-text-secondary">Every upload for {session.bowler_name} is saved as a separate session. When the same bowler uploads another video, it appears here so you can reopen and analyse it without replacing earlier recordings.</p>
    </div>
    <div className="grid gap-3 sm:grid-cols-3">
      <article className="rounded-xl border border-surface-700 bg-surface-800/60 p-4"><p className="text-xs text-text-muted">Saved videos</p><p className="mt-1 text-2xl font-semibold">{entries.length || 1}</p></article>
      <article className="rounded-xl border border-surface-700 bg-surface-800/60 p-4"><p className="text-xs text-text-muted">Analysed videos</p><p className="mt-1 text-2xl font-semibold">{entries.filter((item) => item.analysis_available).length}</p></article>
      <article className="rounded-xl border border-surface-700 bg-surface-800/60 p-4"><p className="text-xs text-text-muted">Current recording</p><p className="mt-1 text-base font-semibold">{historyDate(session.session_date)}</p></article>
    </div>
    {currentInterval && <article className="rounded-xl border border-surface-700 bg-surface-800/60 p-4">
      <h3 className="font-semibold">Selected interval in this video</h3>
      <div className="mt-2 grid grid-cols-3 gap-2 text-sm"><div><p className="text-xs text-text-muted">Start</p><p className="font-semibold">{currentInterval.start_seconds.toFixed(2)} s</p></div><div><p className="text-xs text-text-muted">End</p><p className="font-semibold">{currentInterval.end_seconds.toFixed(2)} s</p></div><div><p className="text-xs text-text-muted">Confidence</p><p className="font-semibold capitalize">{currentInterval.confidence}</p></div></div>
      <p className="mt-2 text-xs text-text-muted">{currentInterval.reason}</p>
    </article>}
    <div className="space-y-3">
      <div><h3 className="font-semibold">All recordings for this bowler</h3><p className="mt-1 text-xs text-text-muted">Old videos remain saved. Select any recording to reopen its video and analysis.</p></div>
      {ordered.length ? <ol className="space-y-3">{ordered.map((item, index) => {
        const isCurrent = item.session.session_id === session.session_id;
        return <li key={item.session.session_id} className={`rounded-2xl border p-4 ${isCurrent ? 'border-brand-500/50 bg-brand-950/10' : 'border-surface-700 bg-surface-800/60'}`}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs text-text-muted">Recording {index + 1} · {historyDate(item.session.session_date)}</p>
              <h4 className="mt-1 truncate font-semibold">{item.session.original_filename}</h4>
              <p className="mt-1 text-xs capitalize text-text-secondary">{item.session.bowling_type} · {item.session.bowling_arm} arm · {item.session.camera_view} view</p>
              <p className="mt-2 text-xs text-text-secondary">{item.analysis_available ? `Pose analysis saved · ${item.detected_frame_count}/${item.sampled_frame_count} frames detected` : 'Video saved · pose analysis not completed yet'}</p>
            </div>
            <div className="flex items-center gap-2">
              {isCurrent && <span className="rounded-full bg-brand-500/15 px-2.5 py-1 text-xs text-brand-300">Current</span>}
              <button type="button" onClick={() => onOpenSession(item.session)} disabled={isCurrent} className="min-h-10 rounded-lg border border-surface-600 px-3 text-xs font-semibold disabled:opacity-40">{isCurrent ? 'Viewing' : 'Open recording'}</button>
            </div>
          </div>
        </li>;
      })}</ol> : <div className="rounded-xl border border-dashed border-surface-600 p-5 text-sm text-text-secondary">No saved history was returned. This recording is still available in the current session.</div>}
    </div>
    {pose && <p className="text-xs text-text-muted">This recording contains {pose.sampled_frame_count} sampled moments. These are analysis frames, not separate ball deliveries.</p>}
  </section>;
}

const LONGITUDINAL_METRICS: { key: string; label: string; mode: 'tilt_variation' | 'absolute_median' | 'median' }[] = [
  { key: 'shoulder_line_tilt', label: 'Shoulder alignment consistency', mode: 'tilt_variation' },
  { key: 'hip_line_tilt', label: 'Hip alignment consistency', mode: 'tilt_variation' },
  { key: 'left_elbow_angle', label: 'Left elbow angle', mode: 'median' },
  { key: 'right_elbow_angle', label: 'Right elbow angle', mode: 'median' },
  { key: 'left_knee_angle', label: 'Left knee angle', mode: 'median' },
  { key: 'right_knee_angle', label: 'Right knee angle', mode: 'median' },
];

function sessionMetricValue(
  entry: BowlerProgressResponse['sessions'][number],
  metric: typeof LONGITUDINAL_METRICS[number],
): number | null {
  const summary = entry.biomechanics_summary?.[metric.key];
  if (!summary || !Number.isFinite(summary.valid_frames) || summary.valid_frames <= 0) return null;
  if (metric.mode === 'tilt_variation') {
    const values = (entry.biomechanics_frames ?? [])
      .map((frame) => frame.measurements?.[metric.key])
      .filter((value): value is number => typeof value === 'number' && Number.isFinite(value))
      .map(Math.abs);
    if (values.length < 2) return null;
    return Math.max(...values) - Math.min(...values);
  }
  if (typeof summary.median !== 'number' || !Number.isFinite(summary.median)) return null;
  if (metric.mode === 'absolute_median') return Math.abs(summary.median);
  return summary.median;
}

function ComparisonPanel({
  pose, history, currentSession,
}: {
  pose: PoseAssessment | null;
  history: BowlerProgressResponse | null;
  currentSession: SessionUploadResponse;
}) {
  const analysed = (Array.isArray(history?.sessions) ? history.sessions : [])
    .filter((entry) => Boolean(entry?.analysis_available && entry.session?.session_id && entry.biomechanics_summary && Array.isArray(entry.biomechanics_frames)))
    .sort((a, b) => (a.session.session_date ?? '').localeCompare(b.session.session_date ?? '')
      || (a.session.created_at ?? '').localeCompare(b.session.created_at ?? ''));
  const [metricKey, setMetricKey] = useState('shoulder_line_tilt');
  const selectedMetric = LONGITUDINAL_METRICS.find((metric) => metric.key === metricKey) ?? LONGITUDINAL_METRICS[0];
  const rows = analysed.map((entry) => ({
    entry,
    value: sessionMetricValue(entry, selectedMetric),
  }));
  const validRows = rows.filter((row): row is typeof rows[number] & { value: number } => typeof row.value === 'number' && Number.isFinite(row.value));
  const maxValue = Math.max(1, ...validRows.map((row) => row.value));
  const previous = validRows.length > 1 ? validRows[validRows.length - 2] : null;
  const latest = validRows.length ? validRows[validRows.length - 1] : null;
  const delta = previous && latest ? latest.value - previous.value : null;
  const isCurrentIncluded = analysed.some((entry) => entry.session.session_id === currentSession.session_id);
  return <section className="space-y-5">
    <div><h2 className="text-lg font-semibold">Long-term bowling progress</h2><p className="mt-1 text-sm text-text-secondary">Compare this bowler's saved, analysed videos in date order. Uploading a second or later video creates another session; earlier recordings and measurements remain available.</p></div>
    <div className="grid gap-3 sm:grid-cols-3">
      <article className="rounded-xl border border-surface-700 bg-surface-800/60 p-4"><p className="text-xs text-text-muted">Total recordings</p><p className="mt-1 text-2xl font-semibold">{history?.sessions.length ?? 0}</p></article>
      <article className="rounded-xl border border-surface-700 bg-surface-800/60 p-4"><p className="text-xs text-text-muted">Analysed recordings</p><p className="mt-1 text-2xl font-semibold">{analysed.length}</p></article>
      <article className="rounded-xl border border-surface-700 bg-surface-800/60 p-4"><p className="text-xs text-text-muted">Current video</p><p className="mt-1 text-sm font-semibold">{historyDate(currentSession.session_date)}</p></article>
    </div>
    {analysed.length < 2 ? <div className="rounded-2xl border border-dashed border-surface-600 p-6">
      <h3 className="font-semibold">Your first progress comparison starts with video two</h3>
      <p className="mt-2 text-sm text-text-secondary">This bowler currently has {analysed.length} analysed recording(s). Once another video for the same bowler is uploaded and pose analysis is completed, this page will compare the measurements across recordings. The first recording is kept as the baseline.</p>
    </div> : <>
      <div className="space-y-2"><label htmlFor="longitudinal-metric" className="text-sm font-medium">Choose what to compare</label><select id="longitudinal-metric" value={metricKey} onChange={(event) => setMetricKey(event.target.value)} className="min-h-11 w-full rounded-xl border border-surface-600 bg-surface-900 px-3 text-sm sm:max-w-md">{LONGITUDINAL_METRICS.map((metric) => <option key={metric.key} value={metric.key}>{metric.label}</option>)}</select>
        <p className="text-xs text-text-muted">{selectedMetric.mode === 'tilt_variation' ? 'Lower variation means the measured line changed less within that video. This describes consistency only; it is not automatically a better technique score.' : 'These are median 2D joint angles for each recording. The app reports the change but does not label a larger or smaller angle as better.'}</p>
      </div>
      <article className="rounded-2xl border border-surface-700 bg-surface-800/60 p-4">
        <h3 className="font-semibold">{selectedMetric.label} across recordings</h3>
        <p className="mt-1 text-xs text-text-muted">{selectedMetric.mode === 'tilt_variation' ? 'Within-video variation in absolute line tilt (degrees)' : 'Median projected angle (degrees)'}</p>
        <div className="mt-4 space-y-4">{rows.map(({ entry, value }, index) => <div key={entry.session.session_id}>
          <div className="mb-1 flex flex-wrap items-center justify-between gap-2 text-xs"><span className="font-medium text-text-primary">Video {index + 1} · {historyDate(entry.session.session_date)}</span><span className="text-text-secondary">{typeof value !== 'number' || !Number.isFinite(value) ? 'Not enough measurements' : `${value.toFixed(1)}°`}</span></div>
          <div className="h-3 overflow-hidden rounded-full bg-surface-900"><div className="h-full rounded-full bg-sky-400" style={{ width: value === null ? '0%' : `${Math.max(2, value / maxValue * 100)}%` }} /></div>
        </div>)}</div>
      </article>
      {latest && <div className="grid gap-3 md:grid-cols-2">
        <article className="rounded-xl border border-surface-700 bg-surface-800/60 p-4">
          <h3 className="font-semibold">Change from the first video (baseline)</h3>
          {(() => {
            const first = validRows[0];
            const baselineDelta = latest.value - first.value;
            if (first === latest) return <p className="mt-2 text-sm text-text-secondary">This is the first analysed recording, so it is the baseline for future comparisons.</p>;
            if (selectedMetric.mode === 'tilt_variation') return <p className="mt-2 text-sm text-text-secondary">{Math.abs(baselineDelta).toFixed(1)}° {baselineDelta < 0 ? 'less' : baselineDelta > 0 ? 'more' : 'no change in'} within-video variation than the first recording. {baselineDelta < 0 ? 'The measured line was more consistent than the baseline.' : baselineDelta > 0 ? 'The measured line varied more than the baseline.' : 'Consistency was unchanged from baseline.'} This is not a validated technique score.</p>;
            return <p className="mt-2 text-sm text-text-secondary">The median angle {baselineDelta < 0 ? 'decreased' : baselineDelta > 0 ? 'increased' : 'did not change'} by {Math.abs(baselineDelta).toFixed(1)}° compared with the first recording. The direction alone does not establish improvement.</p>;
          })()}
        </article>
        <article className="rounded-xl border border-surface-700 bg-surface-800/60 p-4">
          <h3 className="font-semibold">Change from the previous analysed video</h3>
          {delta === null ? <p className="mt-2 text-sm text-text-secondary">There are not enough comparable measurements to calculate a change.</p> : selectedMetric.mode === 'tilt_variation' ? <p className="mt-2 text-sm text-text-secondary">{Math.abs(delta).toFixed(1)}° {delta < 0 ? 'less' : delta > 0 ? 'more' : 'no change in'} within-video variation than the previous analysed recording. {delta < 0 ? 'The line was more consistent in this clip.' : delta > 0 ? 'The line varied more in this clip; review the video to understand why.' : 'The measured variation was unchanged.'} This is a consistency observation, not proof of technique improvement.</p> : <p className="mt-2 text-sm text-text-secondary">The median angle {delta < 0 ? 'decreased' : delta > 0 ? 'increased' : 'did not change'} by {Math.abs(delta).toFixed(1)}° compared with the previous analysed recording. Whether this is beneficial depends on the delivery stage and coach assessment.</p>}
        </article>
      </div>}
      <div className="overflow-x-auto rounded-2xl border border-surface-700">
        <table className="w-full min-w-[620px] text-left text-sm"><thead className="bg-surface-800 text-xs text-text-muted"><tr><th className="p-3">Recording</th><th className="p-3">Date</th><th className="p-3">Median / range</th><th className="p-3">Detected frames</th></tr></thead><tbody>{analysed.map((entry, index) => {
          const summary = entry.biomechanics_summary[selectedMetric.key];
          const value = sessionMetricValue(entry, selectedMetric);
          return <tr key={entry.session.session_id} className="border-t border-surface-700"><td className="p-3">Video {index + 1}{entry.session.session_id === currentSession.session_id ? ' · Current' : ''}</td><td className="p-3">{historyDate(entry.session.session_date)}</td><td className="p-3">{typeof value !== 'number' || !Number.isFinite(value) ? '—' : `${value.toFixed(1)}°`}</td><td className="p-3">{summary ? `${summary.valid_frames}/${summary.sampled_frames}` : '—'}</td></tr>;
        })}</tbody></table>
      </div>
      {!isCurrentIncluded && <p className="text-xs text-amber-300">The current video does not yet have a saved pose assessment in the history. Complete pose analysis to include it in the comparison.</p>}
    </>}
    {pose && <p className="text-xs text-text-muted">Current recording: {pose.detected_frame_count} of {pose.sampled_frame_count} sampled moments had a detected pose. Comparisons use saved analysis summaries from each video.</p>}
  </section>;
}

type SavedCoachFeedback = {
  feedback_id?: string;
  coach_name: string;
  rating: number;
  comment: string;
  delivery_frame_number?: number | null;
  recommendation: string;
  created_at?: string;
};

function ReportPanel({ session, quality, pose }: { session: SessionUploadResponse; quality: QualityAssessment | null; pose: PoseAssessment | null }) {
  const [coach, setCoach] = useState('');
  const [rating, setRating] = useState('4');
  const [comment, setComment] = useState('');
  const [recommendation, setRecommendation] = useState('');
  const [feedback, setFeedback] = useState<SavedCoachFeedback[]>([]);
  const [feedbackLoading, setFeedbackLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState('');
  const [deliveryFrame, setDeliveryFrame] = useState('');

  useEffect(() => {
    let active = true;
    setFeedbackLoading(true);
    fetch(`/api/sessions/${session.session_id}/coach-feedback`)
      .then(async (response) => {
        if (!response.ok) throw new Error('Saved coach feedback could not be loaded.');
        return response.json() as Promise<{ feedback?: SavedCoachFeedback[] }>;
      })
      .then((payload) => { if (active) setFeedback(Array.isArray(payload.feedback) ? payload.feedback : []); })
      .catch(() => { if (active) setStatus('Saved feedback could not be loaded. You can still add new feedback.'); })
      .finally(() => { if (active) setFeedbackLoading(false); });
    return () => { active = false; };
  }, [session.session_id]);

  const insights = pose?.biomechanics ? buildCoachingInsights(pose.biomechanics, session.bowling_arm) : [];
  useEffect(() => {
    const previousTitle = document.title;
    document.title = `${session.bowler_name} - Bowling Progress Report`;
    return () => { document.title = previousTitle; };
  }, [session.bowler_name]);
  // Include every sampled pose frame in the printable report.
  const keyFrames = pose?.frames ?? [];
  const downloadable = feedback.length > 0 && Boolean(pose);

  async function saveFeedback() {
    if (!coach.trim() || !comment.trim()) return;
    setSaving(true);
    setStatus('Saving coach feedback…');
    try {
      const response = await fetch(`/api/sessions/${session.session_id}/coach-feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          coach_name: coach.trim(),
          rating: Number(rating),
          comment: comment.trim(),
          recommendation: recommendation.trim(),
          delivery_frame_number: deliveryFrame ? Number(deliveryFrame) : null,
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({})) as { detail?: string };
        throw new Error(payload.detail || 'Feedback could not be saved.');
      }
      const saved = await response.json() as SavedCoachFeedback;
      setFeedback((current) => [...current, saved]);
      setComment('');
      setRecommendation('');
      setDeliveryFrame('');
      setStatus('Coach feedback saved. Your report is ready to download.');
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Could not save feedback. Check that the backend is running.');
    } finally {
      setSaving(false);
    }
  }

  function downloadReport() {
    if (!downloadable) return;
    window.print();
  }

  return <section className="space-y-5">
    <section className="rounded-2xl border border-brand-500/40 bg-surface-800/80 p-5 print:hidden">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand-300">Step 1 · Coach review</p>
          <h2 className="mt-1 text-xl font-semibold">Add the coach's feedback first</h2>
          <p className="mt-1 max-w-2xl text-sm text-text-secondary">Save the coach's observations and practice advice. They will appear at the top of the printable player report.</p>
        </div>
        <span className="rounded-full bg-surface-900 px-3 py-1 text-xs text-text-secondary">{feedback.length} saved {feedback.length === 1 ? 'review' : 'reviews'}</span>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="text-sm font-medium">Coach name
          <input value={coach} onChange={(event) => setCoach(event.target.value)} placeholder="Enter coach's name" className="mt-1.5 min-h-11 w-full rounded-lg border border-surface-600 bg-surface-900 px-3 text-sm"/>
        </label>
        <label className="text-sm font-medium">Session rating
          <select value={rating} onChange={(event) => setRating(event.target.value)} className="mt-1.5 min-h-11 w-full rounded-lg border border-surface-600 bg-surface-900 px-3 text-sm">{[1,2,3,4,5].map((number) => <option key={number} value={number}>{number} / 5</option>)}</select>
        </label>
        <label className="text-sm font-medium sm:col-span-2">What did the bowler do well? What needs attention?
          <textarea value={comment} onChange={(event) => setComment(event.target.value)} rows={3} placeholder="Write clear, encouraging feedback the player can understand…" className="mt-1.5 w-full rounded-lg border border-surface-600 bg-surface-900 p-3 text-sm"/>
        </label>
        <label className="text-sm font-medium sm:col-span-2">Practice recommendation
          <textarea value={recommendation} onChange={(event) => setRecommendation(event.target.value)} rows={2} placeholder="Add a drill, cue or small change to practise…" className="mt-1.5 w-full rounded-lg border border-surface-600 bg-surface-900 p-3 text-sm"/>
        </label>
        <label className="text-sm font-medium">Frame to review (optional)
          <select value={deliveryFrame} onChange={(event) => setDeliveryFrame(event.target.value)} className="mt-1.5 min-h-11 w-full rounded-lg border border-surface-600 bg-surface-900 px-3 text-sm">
            <option value="">No specific frame</option>
            {(pose?.frames ?? []).map((frame) => <option key={frame.frame_number} value={frame.frame_number}>{frame.timestamp_seconds === null ? `Frame ${frame.frame_number}` : `${frame.timestamp_seconds.toFixed(2)} seconds`}</option>)}
          </select>
        </label>
        <div className="flex items-end">
          <button type="button" onClick={saveFeedback} disabled={saving || !coach.trim() || !comment.trim()} className="min-h-11 w-full rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white disabled:opacity-50">{saving ? 'Saving…' : 'Save coach feedback'}</button>
        </div>
      </div>
      {status && <p role="status" className="mt-3 text-sm text-text-secondary">{status}</p>}
      {feedbackLoading && <p className="mt-2 text-xs text-text-muted">Loading previously saved coach feedback…</p>}
      {feedback.length > 0 && <div className="mt-4 space-y-2">
        <h3 className="text-sm font-semibold">Saved coach reviews</h3>
        {feedback.map((item, index) => <article key={item.feedback_id ?? `${item.coach_name}-${index}`} className="rounded-xl border border-surface-700 bg-surface-900 p-3 text-sm">
          <div className="flex flex-wrap justify-between gap-2"><strong>{item.coach_name}</strong><span className="text-amber-400">{'★'.repeat(item.rating)}{'☆'.repeat(5-item.rating)} · {item.rating}/5</span></div>
          <p className="mt-2 text-text-secondary">{item.comment}</p>
          {item.recommendation && <p className="mt-2 text-text-secondary"><strong className="text-text-primary">Practice:</strong> {item.recommendation}</p>}
        </article>)}
      </div>}
    </section>

    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-surface-700 bg-surface-800/60 p-4 print:hidden">
      <div><p className="font-semibold">Step 2 · Player-friendly report</p><p className="mt-1 text-xs text-text-secondary">Save coach feedback, then download this report as a PDF.</p></div>
      <button type="button" onClick={downloadReport} disabled={!downloadable} className="min-h-11 rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40">Download / print PDF</button>
      {!pose && <p className="w-full text-xs text-amber-300">Complete pose analysis before downloading the full report.</p>}
      {pose && feedback.length === 0 && <p className="w-full text-xs text-amber-300">Save at least one coach review to unlock the PDF download.</p>}
    </div>

    <article className="print-report rounded-2xl bg-white p-5 text-slate-900 shadow-sm sm:p-8">
      <header className="border-b-4 border-emerald-500 pb-5">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-emerald-700">CricketBowlingCoach · Player progress report</p>
        <h1 className="mt-2 text-3xl font-extrabold tracking-tight">{session.bowler_name}</h1>
        <p className="mt-2 text-sm text-slate-600">{session.session_date} · {session.bowling_type} bowler · {session.bowling_arm}-arm action · {session.camera_view} camera view</p>
        <p className="mt-3 text-sm text-slate-700">A simple guide to what went well, what to practise next, and how to make the next bowling session better.</p>
      </header>

      <section className="report-section mt-6 rounded-2xl border-2 border-emerald-200 bg-emerald-50 p-5">
        <p className="text-xs font-bold uppercase tracking-wider text-emerald-800">Coach's feedback · Read this first</p>
        {feedback.length ? feedback.map((item, index) => <div key={item.feedback_id ?? index} className="mt-3 border-b border-emerald-200 pb-3 last:border-0 last:pb-0">
          <div className="flex flex-wrap justify-between gap-2"><h2 className="text-lg font-bold text-slate-900">{item.coach_name}</h2><span className="font-semibold text-amber-700">{item.rating}/5 stars</span></div>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-800">{item.comment}</p>
          {item.recommendation && <p className="mt-2 rounded-lg bg-white/80 p-3 text-sm text-slate-800"><strong>What to practise:</strong> {item.recommendation}</p>}
          {item.delivery_frame_number !== null && item.delivery_frame_number !== undefined && <p className="mt-1 text-xs text-slate-600">Frame selected for review: {item.delivery_frame_number}</p>}
        </div>) : <p className="mt-2 text-sm text-slate-600">No coach review has been saved yet.</p>}
      </section>

      <section className="report-section mt-6">
        <h2 className="text-xl font-bold text-slate-900">Your bowling session at a glance</h2>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-xl bg-slate-100 p-3"><p className="text-xs text-slate-500">Pose detected</p><p className="mt-1 text-xl font-bold">{pose ? `${pose.detected_frame_count}/${pose.sampled_frame_count}` : '—'}</p><p className="text-xs text-slate-500">sampled moments</p></div>
          <div className="rounded-xl bg-slate-100 p-3"><p className="text-xs text-slate-500">Detection coverage</p><p className="mt-1 text-xl font-bold">{pose ? `${pose.overall_frame_detection_coverage_percent.toFixed(0)}%` : '—'}</p></div>
          <div className="rounded-xl bg-slate-100 p-3"><p className="text-xs text-slate-500">Video check</p><p className="mt-1 text-base font-bold">{quality?.overall_assessment === 'suitable' ? 'Ready' : quality?.overall_assessment === 'suitable_with_limitations' ? 'With notes' : quality ? 'Review' : 'Not run'}</p></div>
          <div className="rounded-xl bg-slate-100 p-3"><p className="text-xs text-slate-500">Coach reviews</p><p className="mt-1 text-xl font-bold">{feedback.length}</p></div>
        </div>
        {session.notes && <p className="mt-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-700"><strong>Session note:</strong> {session.notes}</p>}
      </section>

      <section className="report-section mt-7">
        <h2 className="text-xl font-bold text-slate-900">What you are doing well and what to improve</h2>
        <p className="mt-1 text-sm text-slate-600">These notes are based on the landmarks the camera could measure. They are coaching clues, not marks for being a good or bad bowler.</p>
        {insights.length ? <div className="mt-3 space-y-3">{insights.map((item) => <div key={item.id} className="report-card rounded-xl border border-slate-200 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-bold text-slate-900">{item.title}</h3><span className={`rounded-full px-2.5 py-1 text-xs font-bold ${item.status === 'positive' ? 'bg-emerald-100 text-emerald-800' : item.status === 'review' ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-700'}`}>{item.status === 'positive' ? 'A strength' : item.status === 'review' ? 'Practice focus' : 'Needs a coach check'}</span></div>
          <p className="mt-2 text-sm leading-relaxed text-slate-700"><strong>What we noticed:</strong> {item.observation}</p>
          <p className="mt-2 text-sm leading-relaxed text-slate-700"><strong>Try this change:</strong> {item.tryNext}</p>
          <p className="mt-2 text-sm leading-relaxed text-emerald-900"><strong>Why it can help:</strong> {item.benefit}</p>
          <p className="mt-2 text-xs text-slate-500"><strong>Practice cue:</strong> {item.coachCue} · {item.evidence}</p>
        </div>)}</div> : <p className="mt-3 rounded-xl bg-slate-100 p-4 text-sm text-slate-700">There are not enough reliable measurements to create movement-specific advice. Use the frame images below with a coach.</p>}
      </section>

      <section className="report-section mt-7">
        <h2 className="text-xl font-bold text-slate-900">Your bowling movement · Frame by frame</h2>
        <p className="mt-1 text-sm text-slate-600">The blue/yellow skeleton shows the joints MoveNet could identify. Compare the original picture with the detected outline.</p>
        {keyFrames.length ? <div className="mt-3 grid gap-4 sm:grid-cols-2">{keyFrames.map((frame) => <div key={frame.frame_number} className="report-card overflow-hidden rounded-xl border border-slate-200 p-3">
          <h3 className="mb-2 font-bold text-slate-800">{frame.timestamp_seconds === null ? `Frame ${frame.frame_number}` : `${frame.timestamp_seconds.toFixed(2)} seconds`}</h3>
          <div className="grid grid-cols-2 gap-2">
            <figure><img src={frame.original_image_url} alt={`Original bowling frame ${frame.frame_number}`} className="report-image aspect-[3/4] w-full rounded-lg bg-slate-100 object-contain"/><figcaption className="mt-1 text-center text-xs text-slate-500">Original frame</figcaption></figure>
            <figure><img src={frame.overlay_image_url} alt={`Pose skeleton overlay ${frame.frame_number}`} className="report-image aspect-[3/4] w-full rounded-lg bg-slate-100 object-contain"/><figcaption className="mt-1 text-center text-xs text-slate-500">Detected skeleton</figcaption></figure>
          </div>
          <p className="mt-2 text-xs text-slate-500">{frame.detected ? `${frame.keypoints.filter((point) => point.validated_visible).length} validated landmarks visible` : 'No reliable pose detected in this sampled moment.'}</p>
        </div>)}</div> : <p className="mt-3 text-sm text-slate-600">No sampled frame images are available for this report.</p>}
      </section>

      <section className="report-section mt-7">
        <h2 className="text-xl font-bold text-slate-900">Your movement measurements</h2>
        <p className="mt-1 text-sm text-slate-600">Angles are measured in a single camera image. A changing angle is not automatically a mistake.</p>
        {pose?.biomechanics && <div className="mt-3 overflow-hidden rounded-xl border border-slate-200"><table className="w-full text-left text-sm"><thead className="bg-slate-100 text-xs text-slate-600"><tr><th className="p-3">Movement</th><th className="p-3">Typical angle</th><th className="p-3">Frames measured</th></tr></thead><tbody>{Object.entries(pose.biomechanics.summary).map(([key, value]) => <tr key={key} className="border-t border-slate-200"><td className="p-3 capitalize">{key.replaceAll('_',' ')}</td><td className="p-3">{value.median === null ? 'Not available' : `${value.median.toFixed(1)}°`}</td><td className="p-3">{value.valid_frames}/{value.sampled_frames}</td></tr>)}</tbody></table></div>}
      </section>

      <section className="report-section mt-7 rounded-xl bg-sky-50 p-4">
        <h2 className="font-bold text-sky-950">Your next practice plan</h2>
        <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm leading-relaxed text-slate-700">
          <li>Choose one practice focus from the coach's notes or the movement review above.</li>
          <li>Practise it slowly without a ball first. Keep the movement comfortable and controlled.</li>
          <li>Record another video from the same camera position and compare the movement.</li>
          <li>Ask your coach to check whether the change improves your rhythm, balance and repeatability.</li>
        </ol>
      </section>

      <footer className="mt-7 border-t border-slate-200 pt-4 text-xs leading-relaxed text-slate-500">
        This report is an educational aid. A single end-on 2D camera cannot measure true 3D joint rotation, ball speed, target accuracy, bowling legality or injury risk. The illustrated skeleton is based only on visible validated landmarks; missing joints are not guessed. Confirm technique changes with a qualified cricket coach.
      </footer>
    </article>
  </section>;
}
