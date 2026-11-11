/** Application shell: sidebar navigation, top bar and honesty banners. */

import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { api } from '../api/client';
import { useApi } from '../hooks/useApi';
import { useAppConfig } from './AppConfigContext';
import { Badge } from './ui';

interface NavItem {
  to: string;
  label: string;
  icon: string;
  end?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: '▦', end: true },
  { to: '/inbox', label: 'Inbox', icon: '✉' },
  { to: '/customers', label: 'Customers', icon: '👤' },
  { to: '/knowledge', label: 'Knowledge Base', icon: '📚' },
  { to: '/evaluations', label: 'Evaluations', icon: '📊' },
  { to: '/audit', label: 'Audit Logs', icon: '🗒' },
];

const TITLES: Array<[RegExp, string]> = [
  [/^\/$/, 'Dashboard'],
  [/^\/inbox\/\d+/, 'Conversation'],
  [/^\/inbox/, 'Unified Inbox'],
  [/^\/customers\/\d+/, 'Customer 360'],
  [/^\/customers/, 'Customers'],
  [/^\/knowledge/, 'Knowledge Base'],
  [/^\/evaluations/, 'Evaluation'],
  [/^\/audit/, 'Audit Logs'],
];

function pageTitle(pathname: string): string {
  return TITLES.find(([pattern]) => pattern.test(pathname))?.[1] ?? 'AI Case Copilot';
}

export function Layout() {
  const { pathname } = useLocation();
  const { config } = useAppConfig();
  // Drives the review counter in the sidebar. Refetched on navigation so the
  // badge reflects reviews completed elsewhere in the app.
  const { data: dashboard } = useApi(() => api.dashboard(), [pathname]);

  const pendingReview = dashboard?.metrics.pending_human_review ?? 0;
  const demoMode = config?.ai.demo_mode ?? false;

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar__brand">
          <div className="sidebar__brand-name">AI Case Copilot</div>
          <div className="sidebar__brand-sub">
            {config?.brokerage_name ?? 'Correduría Ejemplo'}
          </div>
        </div>

        <nav className="sidebar__nav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                isActive ? 'sidebar__link sidebar__link--active' : 'sidebar__link'
              }
            >
              <span className="sidebar__icon" aria-hidden="true">
                {item.icon}
              </span>
              {item.label}
              {item.to === '/inbox' && pendingReview > 0 && (
                <span className="sidebar__badge">{pendingReview}</span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar__footer">
          <div>Proof of concept</div>
          <div>100% synthetic data</div>
          {config && (
            <div style={{ marginTop: 6 }}>
              {config.ai.llm.model}
              <br />
              vector: {config.vector_backend}
            </div>
          )}
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="topbar__title">{pageTitle(pathname)}</div>
          <div className="topbar__meta">
            {demoMode ? (
              <Badge tone="warning" title="No LLM API key configured — outputs are mock">
                ● Demo AI Mode
              </Badge>
            ) : (
              <Badge tone="success" title={`Live model: ${config?.ai.llm.model}`}>
                ● Live AI — {config?.ai.llm.provider}
              </Badge>
            )}
            <span className="text-xs muted">demo.operator</span>
          </div>
        </header>

        {demoMode && (
          <div className="banner banner--demo">
            <strong>Demo AI Mode.</strong>
            <span>
              No LLM API key is configured, so analyses come from a deterministic mock rule
              engine — not a language model. Set <code>LLM_API_KEY</code> to run the real
              pipeline.
            </span>
          </div>
        )}

        <div className="banner banner--info">
          <strong>Synthetic data.</strong>
          <span>
            Every customer, policy and conversation in this system is invented for
            demonstration purposes. No real personal data is present.
          </span>
        </div>

        <Outlet />
      </main>
    </div>
  );
}
