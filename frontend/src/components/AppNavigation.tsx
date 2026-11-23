import type { ReactNode } from 'react';

export type AppRoute = 'dashboard' | 'bowlers' | 'new-session' | 'sessions' | 'reports' | 'session-workspace';

const items: { route: AppRoute; label: string; shortLabel: string; icon: string }[] = [
  { route: 'dashboard', label: 'Dashboard', shortLabel: 'Home', icon: '⌂' },
  { route: 'bowlers', label: 'Bowlers', shortLabel: 'Bowlers', icon: '◉' },
  { route: 'new-session', label: 'New session', shortLabel: 'New', icon: '+' },
  { route: 'sessions', label: 'Sessions', shortLabel: 'Sessions', icon: '▤' },
  { route: 'reports', label: 'Reports', shortLabel: 'Reports', icon: '▧' },
];

export function AppNavigation({ route, navigate, children }: {
  route: AppRoute;
  navigate: (route: AppRoute) => void;
  children: ReactNode;
}) {
  return <div className="min-h-dvh bg-surface-900 text-text-primary lg:grid lg:grid-cols-[248px_minmax(0,1fr)]">
    <aside className="hidden border-r border-surface-700/70 bg-surface-900 px-4 py-6 lg:flex lg:flex-col">
      <div className="mb-9 flex items-center gap-3 px-2"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 font-bold text-white">BC</div><div><p className="font-bold tracking-tight">BowlCoach</p><p className="text-xs text-text-muted">Coaching workspace</p></div></div>
      <nav aria-label="Main navigation" className="space-y-1">{items.map((item) => <button key={item.route} type="button" onClick={() => navigate(item.route)} aria-current={route === item.route ? 'page' : undefined} className={`flex min-h-12 w-full items-center gap-3 rounded-xl px-3 text-left text-sm font-medium transition ${route === item.route || (route === 'session-workspace' && item.route === 'sessions') ? 'bg-brand-500/10 text-brand-300' : 'text-text-secondary hover:bg-surface-800 hover:text-text-primary'}`}><span className="w-6 text-center text-lg" aria-hidden="true">{item.icon}</span>{item.label}</button>)}</nav>
      <div className="mt-auto rounded-xl border border-surface-700 bg-surface-800/60 p-3 text-xs leading-relaxed text-text-muted">A visual workspace for reviewing cricket bowling sessions.</div>
    </aside>
    <div className="min-w-0 pb-20 lg:pb-0">
      <header className="sticky top-0 z-20 border-b border-surface-700/70 bg-surface-900/95 px-4 py-3 backdrop-blur lg:hidden"><div className="flex items-center gap-2"><div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-xs font-bold">BC</div><span className="font-semibold">BowlCoach</span></div></header>
      {children}
      <nav aria-label="Main navigation" className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-surface-700 bg-surface-900/95 px-1 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">{items.map((item) => <button key={item.route} type="button" onClick={() => navigate(item.route)} aria-current={route === item.route ? 'page' : undefined} className={`flex min-h-16 flex-col items-center justify-center gap-0.5 px-1 text-[10px] font-medium ${route === item.route || (route === 'session-workspace' && item.route === 'sessions') ? 'text-brand-300' : 'text-text-muted'}`}><span className="text-lg" aria-hidden="true">{item.icon}</span><span>{item.shortLabel}</span></button>)}</nav>
    </div>
  </div>;
}

export function PageHeader({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: ReactNode }) {
  return <div className="mb-6 flex flex-wrap items-start justify-between gap-4"><div>{eyebrow && <p className="text-xs font-semibold uppercase tracking-widest text-brand-400">{eyebrow}</p>}<h1 className="mt-1 text-2xl font-bold tracking-tight text-text-primary sm:text-3xl">{title}</h1>{description && <p className="mt-2 max-w-3xl text-sm leading-relaxed text-text-secondary">{description}</p>}</div>{action}</div>;
}
