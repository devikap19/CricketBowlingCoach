import type { SessionUploadResponse } from '../types';
import { PageHeader, type AppRoute } from '../components/AppNavigation';

function dateLabel(value: string) {
  const parsed = new Date(`${value.slice(0, 10)}T12:00:00`);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function SessionCard({ session, onOpen }: { session: SessionUploadResponse; onOpen: (session: SessionUploadResponse) => void }) {
  return <button type="button" onClick={() => onOpen(session)} className="w-full rounded-2xl border border-surface-700 bg-surface-800/60 p-4 text-left transition hover:border-brand-500/60 hover:bg-surface-800"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-semibold text-text-primary">{session.bowler_name}</p><p className="mt-1 text-sm text-text-secondary">{dateLabel(session.session_date)} · <span className="capitalize">{session.bowling_type}</span> · {session.bowling_arm} arm</p></div><span className="rounded-full bg-surface-700 px-3 py-1 text-xs text-text-secondary">Open session</span></div><p className="mt-3 text-xs capitalize text-text-muted">{session.camera_view} camera view</p></button>;
}

export function DashboardPage({ sessions, onNavigate, onOpenSession }: { sessions: SessionUploadResponse[]; onNavigate: (route: AppRoute) => void; onOpenSession: (session: SessionUploadResponse) => void }) {
  const bowlers = new Set(sessions.map((session) => session.bowler_name.trim().toLocaleLowerCase())).size;
  return <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
    <PageHeader eyebrow="Coach dashboard" title="Good session review starts here" description="Create a bowling session, revisit saved recordings, and inspect the visual results that are available." action={<button type="button" onClick={() => onNavigate('new-session')} className="min-h-12 rounded-xl bg-brand-600 px-5 text-sm font-semibold text-white hover:bg-brand-500">＋ New session</button>} />
    <div className="grid gap-3 sm:grid-cols-3"><article className="rounded-2xl border border-surface-700 bg-surface-800/60 p-5"><p className="text-sm text-text-muted">Saved sessions</p><p className="mt-2 text-3xl font-bold">{sessions.length}</p><button type="button" onClick={() => onNavigate('sessions')} className="mt-3 text-sm font-medium text-brand-300">Browse sessions →</button></article><article className="rounded-2xl border border-surface-700 bg-surface-800/60 p-5"><p className="text-sm text-text-muted">Bowlers</p><p className="mt-2 text-3xl font-bold">{bowlers}</p><button type="button" onClick={() => onNavigate('bowlers')} className="mt-3 text-sm font-medium text-brand-300">View bowlers →</button></article><article className="rounded-2xl border border-surface-700 bg-surface-800/60 p-5"><p className="text-sm text-text-muted">Coaching reports</p><p className="mt-2 text-lg font-semibold">Visual review available</p><p className="mt-2 text-sm text-text-secondary">Technique observations and comparisons are not available yet.</p></article></div>
    <section className="mt-8"><div className="mb-3 flex items-center justify-between gap-3"><h2 className="text-lg font-semibold">Recent sessions</h2>{sessions.length > 0 && <button type="button" onClick={() => onNavigate('sessions')} className="text-sm text-brand-300">See all</button>}</div>{sessions.length ? <div className="grid gap-3 md:grid-cols-2">{sessions.slice(0, 4).map((session) => <SessionCard key={session.session_id} session={session} onOpen={onOpenSession} />)}</div> : <div className="rounded-2xl border border-dashed border-surface-600 bg-surface-800/30 p-8 text-center"><p className="font-medium">No sessions yet</p><p className="mt-2 text-sm text-text-secondary">Create a session to start reviewing a bowler’s video.</p><button type="button" onClick={() => onNavigate('new-session')} className="mt-4 min-h-11 rounded-xl bg-brand-600 px-4 text-sm font-semibold">Create first session</button></div>}</section>
  </main>;
}

export function SessionsPage({ sessions, onOpenSession }: { sessions: SessionUploadResponse[]; onOpenSession: (session: SessionUploadResponse) => void }) {
  return <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-10"><PageHeader eyebrow="Library" title="Sessions" description="Your saved bowling recordings and session details." />{sessions.length ? <div className="grid gap-3 md:grid-cols-2">{sessions.map((session) => <SessionCard key={session.session_id} session={session} onOpen={onOpenSession} />)}</div> : <Empty title="No saved sessions" detail="Uploaded sessions will appear here." />}</main>;
}

export function BowlersPage({ sessions, onOpenSession, onNewSession }: { sessions: SessionUploadResponse[]; onOpenSession: (session: SessionUploadResponse) => void; onNewSession: () => void }) {
  const groups = new Map<string, SessionUploadResponse[]>();
  for (const session of sessions) groups.set(session.bowler_name.trim().toLocaleLowerCase(), [...(groups.get(session.bowler_name.trim().toLocaleLowerCase()) ?? []), session]);
  const bowlers = [...groups.values()].map((items) => items.sort((a, b) => b.session_date.localeCompare(a.session_date)));
  return <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-10"><PageHeader eyebrow="Roster" title="Bowlers" description="Bowler profiles are created from saved session records. Add a session to include a bowler here." action={<button type="button" onClick={onNewSession} className="min-h-11 rounded-xl bg-brand-600 px-4 text-sm font-semibold">＋ New session</button>} />{bowlers.length ? <div className="grid gap-4 md:grid-cols-2">{bowlers.map((items) => { const latest = items[0]; return <article key={latest.bowler_name.toLocaleLowerCase()} className="rounded-2xl border border-surface-700 bg-surface-800/60 p-5"><div className="flex items-start justify-between gap-3"><div><h2 className="text-lg font-semibold">{latest.bowler_name}</h2><p className="mt-1 text-sm text-text-secondary">{items.length} {items.length === 1 ? 'session' : 'sessions'}</p></div><span className="rounded-full bg-surface-700 px-3 py-1 text-xs capitalize text-text-secondary">{latest.bowling_arm} arm · {latest.bowling_type}</span></div><button type="button" onClick={() => onOpenSession(latest)} className="mt-4 min-h-10 text-sm font-medium text-brand-300">Open latest session →</button></article>; })}</div> : <Empty title="No bowlers yet" detail="Bowler profiles appear after you create their first session." />}</main>;
}

export function ReportsPage({ sessions, onOpenSession }: { sessions: SessionUploadResponse[]; onOpenSession: (session: SessionUploadResponse) => void }) {
  return <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-10"><PageHeader eyebrow="Reports" title="Session reports" description="Open a session to see its available recording and pose review in one place." />{sessions.length ? <div className="grid gap-3 md:grid-cols-2">{sessions.map((session) => <SessionCard key={session.session_id} session={session} onOpen={onOpenSession} />)}</div> : <Empty title="No reports yet" detail="Reports will be available after a session has recording and pose results." />}</main>;
}

function Empty({ title, detail }: { title: string; detail: string }) {
  return <div className="rounded-2xl border border-dashed border-surface-600 bg-surface-800/30 p-8 text-center"><p className="font-medium">{title}</p><p className="mt-2 text-sm text-text-secondary">{detail}</p></div>;
}
