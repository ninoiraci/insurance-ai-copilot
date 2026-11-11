/** Append-only audit trail: every AI decision and every human sign-off. */

import { useState } from 'react';
import { api } from '../api/client';
import { useApi } from '../hooks/useApi';
import { Badge, EmptyState, ErrorState, Loading, Panel } from '../components/ui';
import { formatDateTime, humanise, type Tone } from '../utils/format';

function actionTone(action: string): Tone {
  if (action.includes('FAILED') || action.includes('INJECTION')) return 'danger';
  if (action.includes('OVERRIDE')) return 'warning';
  if (action.includes('REVIEW') || action.includes('SIMULATED_SEND')) return 'success';
  if (action.includes('EVALUATION') || action.includes('KNOWLEDGE')) return 'info';
  return 'neutral';
}

export function AuditLogsPage() {
  const [action, setAction] = useState('');
  const { data, loading, error, refetch } = useApi(
    () => api.auditLogs(action || undefined),
    [action],
  );

  return (
    <div className="page stack">
      <div className="page__header">
        <div>
          <h1>Audit logs</h1>
          <p className="page__subtitle">
            Every AI analysis, rule override, safety flag, task and human decision is
            recorded with its request id. Message bodies and draft responses are deliberately
            never written to the audit trail.
          </p>
        </div>
        <button type="button" className="btn btn--sm" onClick={refetch}>
          Refresh
        </button>
      </div>

      <Panel title="Filter">
        <div className="filters">
          <div className="field" style={{ minWidth: 280 }}>
            <label className="field__label" htmlFor="audit-action">
              Action
            </label>
            <select
              id="audit-action"
              className="select"
              value={action}
              onChange={(event) => setAction(event.target.value)}
            >
              <option value="">All actions</option>
              {data?.actions.map((value) => (
                <option key={value} value={value}>
                  {humanise(value)}
                </option>
              ))}
            </select>
          </div>
          {action && (
            <button type="button" className="btn btn--sm" onClick={() => setAction('')}>
              Clear
            </button>
          )}
        </div>
      </Panel>

      <Panel title="Trail" hint={data ? `${data.count} entries` : undefined} flush>
        {loading && <Loading />}
        {error && !loading && (
          <div style={{ padding: 16 }}>
            <ErrorState message={error} onRetry={refetch} />
          </div>
        )}
        {data && !loading && data.items.length === 0 && (
          <EmptyState
            title="No audit entries"
            hint="Run an analysis or an evaluation to generate the trail."
          />
        )}
        {data && !loading && data.items.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Action</th>
                  <th>Entity</th>
                  <th>Actor</th>
                  <th>Request</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((entry) => (
                  <tr key={entry.id}>
                    <td className="table__muted nowrap">{formatDateTime(entry.timestamp)}</td>
                    <td>
                      <Badge tone={actionTone(entry.action)}>{humanise(entry.action)}</Badge>
                    </td>
                    <td className="mono text-xs nowrap">
                      {entry.entity_type}
                      {entry.entity_id !== null && `#${entry.entity_id}`}
                    </td>
                    <td className="table__muted">{entry.actor}</td>
                    <td className="mono text-xs">{entry.request_id ?? '—'}</td>
                    <td>
                      {Object.keys(entry.metadata).length === 0 ? (
                        <span className="table__muted">—</span>
                      ) : (
                        <details>
                          <summary className="text-xs" style={{ cursor: 'pointer' }}>
                            {Object.keys(entry.metadata).length} fields
                          </summary>
                          <pre
                            className="mono pre-wrap"
                            style={{ margin: '6px 0 0', color: 'var(--text-secondary)' }}
                          >
                            {JSON.stringify(entry.metadata, null, 2)}
                          </pre>
                        </details>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
