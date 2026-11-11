/** Operational overview: queue health, AI throughput and review statistics. */

import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useApi } from '../hooks/useApi';
import {
  BarList,
  Badge,
  ErrorState,
  EmptyState,
  Loading,
  Panel,
  Stat,
} from '../components/ui';
import {
  channelIcon,
  humanise,
  percent,
  relativeTime,
  statusTone,
  urgencyTone,
} from '../utils/format';

export function DashboardPage() {
  const navigate = useNavigate();
  const { data, loading, error, refetch } = useApi(() => api.dashboard(), []);

  if (loading) return <div className="page"><Loading label="Loading dashboard…" /></div>;
  if (error) return <div className="page"><ErrorState message={error} onRetry={refetch} /></div>;
  if (!data) return null;

  const { metrics, distributions, human_review: review, recent_conversations: recent } = data;

  return (
    <div className="page stack">
      <div className="page__header">
        <div>
          <h1>Operations dashboard</h1>
          <p className="page__subtitle">
            Live state of the multi-channel queue and of the AI layer that triages it.
          </p>
        </div>
        <button type="button" className="btn btn--sm" onClick={refetch}>
          Refresh
        </button>
      </div>

      <div className="grid grid--stats">
        <Stat
          label="Open conversations"
          value={metrics.open_conversations}
          hint={`${metrics.total_conversations} total in the system`}
        />
        <Stat
          label="AI processed (24h)"
          value={metrics.ai_processed_last_24h}
          hint="Analyses created in the last day"
        />
        <Stat
          label="Awaiting human review"
          value={metrics.pending_human_review}
          variant={metrics.pending_human_review > 0 ? 'warning' : undefined}
          hint="Drafts blocked until an operator signs off"
        />
        <Stat
          label="High / critical cases"
          value={metrics.high_priority_cases}
          variant={metrics.high_priority_cases > 0 ? 'danger' : undefined}
          hint="Urgency raised by the rule engine"
        />
        <Stat
          label="Avg. confidence"
          value={percent(metrics.avg_confidence, 0)}
          hint="Mean classification confidence"
        />
        <Stat
          label="Avg. AI latency"
          value={`${metrics.avg_latency_ms} ms`}
          hint="Full pipeline, end to end"
        />
        <Stat
          label="Approval rate"
          value={metrics.approval_rate === null ? '—' : percent(metrics.approval_rate, 0)}
          hint={
            metrics.reviews_recorded === 0
              ? 'No reviews recorded yet'
              : `${metrics.reviews_recorded} reviews recorded`
          }
        />
        <Stat
          label="Open tasks"
          value={metrics.open_tasks}
          hint="Work items created by the action engine"
        />
      </div>

      <div className="grid grid--two">
        <Panel title="Intent distribution" hint="across all analyses">
          <BarList items={distributions.intent.map((item) => ({
            label: humanise(item.label),
            count: item.count,
          }))} emptyLabel="No analyses yet — run one from the Inbox" />
        </Panel>

        <Panel title="Urgency distribution" hint="after deterministic rules">
          <BarList items={distributions.urgency.map((item) => ({
            label: humanise(item.label),
            count: item.count,
          }))} emptyLabel="No analyses yet" />
        </Panel>

        <Panel title="Channel mix" hint="inbound conversations">
          <BarList items={distributions.channel.map((item) => ({
            label: humanise(item.label),
            count: item.count,
          }))} />
        </Panel>

        <Panel title="Human-in-the-loop" hint="review outcomes">
          <div className="grid grid--stats" style={{ gap: 12 }}>
            <Stat label="Review required" value={review.required} />
            <Stat label="Approved" value={review.approved} variant="success" />
            <Stat label="Edited" value={review.edited} variant="warning" />
            <Stat label="Rejected" value={review.rejected} variant="danger" />
          </div>
          <p className="text-xs muted mt-md">
            Nothing is ever sent to a customer automatically. Approval records the decision
            only — this proof of concept simulates delivery.
          </p>
        </Panel>
      </div>

      <Panel
        title="Recent conversations"
        actions={<Link className="btn btn--sm" to="/inbox">Open inbox</Link>}
        flush
      >
        {recent.length === 0 ? (
          <EmptyState title="No conversations" hint="Seed the demo data to populate the inbox." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Customer</th>
                  <th>Channel</th>
                  <th>Subject</th>
                  <th>Intent</th>
                  <th>Urgency</th>
                  <th>Status</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((conversation) => (
                  <tr
                    key={conversation.id}
                    className="is-clickable"
                    onClick={() => navigate(`/inbox/${conversation.id}`)}
                  >
                    <td className="table__primary">{conversation.customer_name}</td>
                    <td className="nowrap">
                      {channelIcon(conversation.channel)} {humanise(conversation.channel)}
                    </td>
                    <td className="table__preview">{conversation.subject}</td>
                    <td>
                      {conversation.latest_analysis ? (
                        <Badge tone="accent">
                          {humanise(conversation.latest_analysis.intent)}
                        </Badge>
                      ) : (
                        <span className="table__muted">Not analysed</span>
                      )}
                    </td>
                    <td>
                      {conversation.latest_analysis ? (
                        <Badge tone={urgencyTone[conversation.latest_analysis.urgency]}>
                          {conversation.latest_analysis.urgency}
                        </Badge>
                      ) : (
                        <span className="table__muted">—</span>
                      )}
                    </td>
                    <td>
                      <Badge tone={statusTone(conversation.status)}>
                        {humanise(conversation.status)}
                      </Badge>
                    </td>
                    <td className="table__muted nowrap">
                      {relativeTime(conversation.updated_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="System" hint="knowledge base and data volume">
        <div className="grid grid--stats" style={{ gap: 12 }}>
          <Stat label="Customers" value={metrics.customers} />
          <Stat label="Policies" value={metrics.policies} />
          <Stat label="KB documents" value={metrics.knowledge_documents} />
          <Stat label="KB chunks" value={metrics.knowledge_chunks} hint="embedded and searchable" />
        </div>
      </Panel>
    </div>
  );
}
