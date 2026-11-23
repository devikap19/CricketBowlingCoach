import { useRef, useState, type PointerEvent } from 'react';
import { sessionVideoUrl, trackingPreviewUrl } from '../services/api';
import type { ActiveInterval, SessionUploadResponse, TrackBox, TrackingAssessment } from '../types';

function timeLabel(value: number) {
  return `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, '0')}.${String(Math.round((value % 1) * 10))}`;
}

export function VideoWorkspace({ session, tracking, stage, busy, error, onTrack, onConfirm, onRedraw, onContinue }: {
  session: SessionUploadResponse;
  tracking: TrackingAssessment | null;
  stage: 'select' | 'tracking' | 'review';
  busy: boolean;
  error: string | null;
  onTrack: (time: number, box: TrackBox) => void;
  onConfirm: (start: number, end: number) => void;
  onRedraw: () => void;
  onContinue: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [drawing, setDrawing] = useState(false);
  const [anchor, setAnchor] = useState<{ x: number; y: number } | null>(null);
  const [selection, setSelection] = useState<TrackBox | null>(null);
  const initialInterval = tracking?.confirmed_interval ?? tracking?.proposed_intervals[0];
  const [startText, setStartText] = useState(initialInterval?.start_seconds.toFixed(1) ?? '');
  const [endText, setEndText] = useState(initialInterval?.end_seconds.toFixed(1) ?? '');
  const [chosenInterval, setChosenInterval] = useState<ActiveInterval | null>(initialInterval ?? null);

  const displayedPoint = tracking?.track.length ? tracking.track.reduce((best, point) => Math.abs(point.timestamp_seconds - time) < Math.abs(best.timestamp_seconds - time) ? point : best, tracking.track[0]) : null;
  const displayBox = displayedPoint?.box ?? selection;
  const rangeValid = Number.isFinite(Number(startText)) && Number.isFinite(Number(endText)) && Number(startText) >= (tracking?.selected_at_seconds ?? 0) && Number(startText) < Number(endText) && Number(endText) <= (tracking?.duration_seconds ?? duration);

  function normalizedPoint(event: PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return { x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)), y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)) };
  }

  function pointerDown(event: PointerEvent<HTMLDivElement>) {
    if (stage !== 'select' || !drawing) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    const point = normalizedPoint(event);
    setAnchor(point);
    setSelection({ ...point, width: 0, height: 0 });
  }

  function pointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!drawing || !anchor) return;
    const point = normalizedPoint(event);
    setSelection({ x: Math.min(anchor.x, point.x), y: Math.min(anchor.y, point.y), width: Math.abs(anchor.x - point.x), height: Math.abs(anchor.y - point.y) });
  }

  function pointerUp(event: PointerEvent<HTMLDivElement>) {
    if (!drawing || !anchor) return;
    const point = normalizedPoint(event);
    const box = { x: Math.min(anchor.x, point.x), y: Math.min(anchor.y, point.y), width: Math.abs(anchor.x - point.x), height: Math.abs(anchor.y - point.y) };
    setSelection(box.width >= .015 && box.height >= .02 ? box : null);
    setAnchor(null);
    setDrawing(false);
  }

  function setVideoTime(value: number) {
    if (videoRef.current) videoRef.current.currentTime = value;
    setTime(value);
  }

  const representativePoints = tracking?.track.length ? [tracking.track[0], tracking.track[Math.floor(tracking.track.length / 2)], tracking.track[tracking.track.length - 1]].filter((point, index, all) => all.findIndex((candidate) => candidate.frame_number === point.frame_number) === index) : [];

  return <section className="space-y-5" aria-label="Video workspace">
    <div className="overflow-hidden rounded-2xl border border-surface-700 bg-black">
      <div className="flex min-h-64 max-h-[68vh] w-full items-center justify-center overflow-hidden">
        <div className="relative inline-block max-h-[68vh] max-w-full" onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={pointerUp} style={{ touchAction: drawing ? 'none' : 'auto' }}>
          <video ref={videoRef} src={sessionVideoUrl(session.session_id)} controls={!drawing} playsInline preload="metadata" onLoadedMetadata={(event) => { setDuration(event.currentTarget.duration || 0); setTime(event.currentTarget.currentTime); }} onTimeUpdate={(event) => setTime(event.currentTarget.currentTime)} className="block max-h-[68vh] max-w-full w-auto object-contain" />
          {displayBox && <div className={`pointer-events-none absolute border-2 ${displayedPoint && displayedPoint.status !== 'tracked' ? 'border-accent-amber' : 'border-brand-400'} bg-brand-400/15`} style={{ left: `${displayBox.x * 100}%`, top: `${displayBox.y * 100}%`, width: `${displayBox.width * 100}%`, height: `${displayBox.height * 100}%` }} />}
          {drawing && <div className="absolute inset-0 cursor-crosshair" />}
        </div>
      </div>
      <div className="space-y-3 border-t border-surface-700 bg-surface-900 p-4">
        <div className="flex items-center justify-between gap-3 text-xs text-text-secondary"><span>Video position</span><span>{timeLabel(time)}{duration ? ` / ${timeLabel(duration)}` : ''}</span></div>
        <input aria-label="Video timeline" type="range" min="0" max={Math.max(duration, .1)} step="0.1" value={Math.min(time, duration || 0)} onChange={(event) => setVideoTime(Number(event.target.value))} className="min-h-8 w-full accent-brand-500" />
        {stage !== 'select' && <p className="text-sm text-text-secondary">{displayedPoint ? displayedPoint.status === 'tracked' ? 'Selected bowler is visible in the tracking sample.' : 'The bowler could not be followed confidently at this sample.' : 'Play or scrub the video to review the selected bowler.'}</p>}
      </div>
    </div>

    {stage === 'select' && <div className="rounded-2xl border border-surface-700 bg-surface-800/60 p-4 sm:p-5"><h2 className="font-semibold">Select the bowler</h2><p className="mt-1 text-sm text-text-secondary">Pause on a clear frame, draw a box around the bowler, then choose Track Bowler. You can redraw the box before tracking.</p><div className="mt-4 flex flex-wrap gap-2"><button type="button" onClick={() => { videoRef.current?.pause(); setSelection(null); setDrawing(true); }} className="min-h-11 rounded-xl border border-surface-600 px-4 text-sm font-medium hover:bg-surface-700">{selection ? 'Redraw selection' : 'Draw selection box'}</button>{drawing && <button type="button" onClick={() => { setDrawing(false); setAnchor(null); }} className="min-h-11 rounded-xl border border-surface-600 px-4 text-sm">Cancel</button>}<button type="button" disabled={!selection || selection.width < .015 || selection.height < .02 || busy} onClick={() => selection && onTrack(time, selection)} className="min-h-11 rounded-xl bg-brand-600 px-5 text-sm font-semibold text-white disabled:opacity-40">{busy ? 'Tracking bowler…' : 'Track Bowler'}</button></div>{selection && <p className="mt-3 text-sm text-brand-300">Bowler selected in the video. Review the highlighted box, then track this person.</p>}{error && <p role="alert" className="mt-3 rounded-xl border border-accent-red/40 bg-red-950/30 p-3 text-sm text-red-200">{error}</p>}</div>}

    {stage === 'tracking' && <div className="space-y-4 rounded-2xl border border-surface-700 bg-surface-800/60 p-4 sm:p-5"><div><h2 className="font-semibold">Tracking review</h2><p className="mt-1 text-sm text-text-secondary">Check that the highlighted box continues to follow the selected bowler throughout the recording.</p></div>{busy && <div role="status" className="rounded-xl bg-surface-900 p-4"><p className="text-sm text-text-primary">Following the selected bowler through the video…</p><progress className="mt-3 h-2 w-full accent-brand-500" /></div>}{error && <p role="alert" className="rounded-xl border border-accent-red/40 bg-red-950/30 p-3 text-sm text-red-200">{error}</p>}{tracking && <><p className="rounded-xl border border-surface-700 bg-surface-900 p-3 text-sm text-text-secondary">{tracking.tracking_interruptions.length ? `The bowler was difficult to follow in ${tracking.tracking_interruptions.length} section(s). Review the marked moments.` : 'Tracking completed. Review the highlighted bowler in the video before continuing.'} The system follows your selection and does not independently verify identity.</p><div className="grid gap-3 sm:grid-cols-3">{representativePoints.map((point) => <figure key={point.frame_number} className="overflow-hidden rounded-xl bg-surface-900"><img loading="lazy" src={trackingPreviewUrl(session.session_id, point.frame_number)} alt={`Tracking review frame at ${point.timestamp_seconds.toFixed(1)} seconds`} className="aspect-video w-full object-contain bg-black"/><figcaption className="p-3 text-xs text-text-secondary">{timeLabel(point.timestamp_seconds)} · {point.status === 'tracked' ? 'Bowler followed' : 'Review this moment'}</figcaption></figure>)}</div><div className="flex flex-wrap gap-2"><button type="button" onClick={onRedraw} className="min-h-11 rounded-xl border border-surface-600 px-4 text-sm">Go back and redraw selection</button><button type="button" onClick={onContinue} className="min-h-11 rounded-xl bg-brand-600 px-5 text-sm font-semibold">Review video</button></div></>}</div>}

    {stage === 'review' && tracking && <div className="space-y-4 rounded-2xl border border-surface-700 bg-surface-800/60 p-4 sm:p-5"><div><h2 className="font-semibold">Review video and confirm delivery interval</h2><p className="mt-1 text-sm text-text-secondary">Play the video and inspect the highlighted bowler. Adjust the interval to cover the delivery you want to review.</p></div><div className="flex flex-wrap gap-2"><button type="button" onClick={onRedraw} className="min-h-11 rounded-xl border border-surface-600 px-4 text-sm">Redraw bowler selection</button>{tracking.confirmed_interval && <span className="self-center rounded-full bg-brand-500/10 px-3 py-2 text-sm text-brand-300">Interval confirmed: {timeLabel(tracking.confirmed_interval.start_seconds)}–{timeLabel(tracking.confirmed_interval.end_seconds)}</span>}</div>{tracking.proposed_intervals.length > 0 && <div className="space-y-2"><h3 className="text-sm font-medium">Suggested delivery intervals</h3>{tracking.proposed_intervals.map((interval, index) => <button key={`${interval.start_seconds}-${index}`} type="button" onClick={() => { setChosenInterval(interval); setStartText(interval.start_seconds.toFixed(1)); setEndText(interval.end_seconds.toFixed(1)); }} className={`block min-h-11 w-full rounded-xl border px-3 text-left text-sm ${chosenInterval === interval ? 'border-brand-400 bg-brand-500/10' : 'border-surface-600 text-text-secondary'}`}>Interval {index + 1}: {timeLabel(interval.start_seconds)}–{timeLabel(interval.end_seconds)}</button>)}</div>}{tracking.proposed_intervals.length === 0 && <p className="rounded-xl bg-surface-900 p-3 text-sm text-text-secondary">No delivery interval was suggested. Set the start and end times using the video, then confirm the range.</p>}<div className="grid grid-cols-2 gap-3"><label className="text-sm text-text-secondary">Start time (seconds)<input type="number" min={tracking.selected_at_seconds} max={tracking.duration_seconds} step="0.1" value={startText} onChange={(event) => { setStartText(event.target.value); setChosenInterval(null); }} className="mt-1 min-h-11 w-full rounded-xl border border-surface-600 bg-surface-900 px-3 text-base text-text-primary"/></label><label className="text-sm text-text-secondary">End time (seconds)<input type="number" min={tracking.selected_at_seconds} max={tracking.duration_seconds} step="0.1" value={endText} onChange={(event) => { setEndText(event.target.value); setChosenInterval(null); }} className="mt-1 min-h-11 w-full rounded-xl border border-surface-600 bg-surface-900 px-3 text-base text-text-primary"/></label></div>{error && <p role="alert" className="text-sm text-accent-red">{error}</p>}<button type="button" disabled={!rangeValid || busy} onClick={() => onConfirm(Number(startText), Number(endText))} className="min-h-12 w-full rounded-xl border border-surface-600 px-4 text-sm font-semibold disabled:opacity-40">{busy ? 'Saving interval…' : tracking.confirmed_interval ? 'Confirm updated interval' : 'Confirm selection and interval'}</button><button type="button" disabled={!tracking.confirmed_interval} onClick={onContinue} className="min-h-12 w-full rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white disabled:opacity-40">Continue to Analysis</button></div>}
  </section>;
}
