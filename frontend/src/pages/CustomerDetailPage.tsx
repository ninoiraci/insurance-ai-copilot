/** Customer 360 record: profile, policies, conversations, tasks, AI history. */

import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useApi } from '../hooks/useApi';
import { Badge, EmptyState, ErrorState, Loading, Panel, Stat } from '../components/ui';
import {
  channelIcon,
  countLabel,
  expiryTone,
  formatDate,
  formatDateTime,
  humanise,
  percent,
  statusTone,
  urgencyTone,
} from '../utils/format';

export function CustomerDetailPage() {
  const { customerId } = useParams();
  const navigate = useNavigate();
  const id = Number(customerId);

  const { data, loading, error, refetch } = useApi(() => api.customer(id), [id]);

  if (Number.isNaN(id)) {
    return <div className="page"><ErrorState message="Invalid customer id." /></div>;
  }
  if (loading) return <div className="page"><Loading /></div>;
  if (error) return <div className="page"><ErrorState message={error} onRetry={refetch} /></div>;
  if (!data) return null;

  const openTasks = data.tasks.filter((task) => task.status !== 'DONE');

  return (
    <div className="page stack">
      <div className="page__header">
        <div>
          <div className="text-sm muted" style={{ marginBottom: 4 }}>
            <Link to="/customers">← Customers</Link>
          </div>
          <h1>{data.full_name}</h1>
          <p className="page__subtitle">
            {data.email} · {data.phone} · {data.city} · customer since{' '}
            {formatDate(data.created_at)}
          </p>
        </div>
      </div>

      <div className="grid grid--stats">
        <Stat label="Policies" value={data.policies.length} />
        <Stat label="Conversations" value={data.conversations.length} />
        <Stat
          label="Open tasks"
          value={openTasks.length}
          variant={openTasks.length > 0 ? 'warning' : undefined}
        />
        <Stat label="AI analyses" value={data.ai_case_history.length} />
      </div>

      <div className="grid grid--two">
        <Panel title="Policies" hint={`${data.policies.length} on record`} flush>
          {data.policies.length === 0 ? (
            <EmptyState title="No policies" />
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Number</th>
                    <th>Type</th>
                    <th>Provider</th>
                    <th>Status</th>
                    <th>Expires</th>
                    <th>Premium</th>
                  </tr>
                </thead>
                <tbody>
                  {data.policies.map((policy) => (
                    <tr key={policy.id}>
                      <td className="mono">{policy.policy_number}</td>
                      <td>{humanise(policy.policy_type)}</td>
                      <td className="table__muted">{policy.provider}</td>
                      <td>
                        <Badge tone={statusTone(policy.status)}>
                          {humanise(policy.status)}
                        </Badge>
                      </td>
                      <td className="nowrap">
                        <Badge tone={expiryTone(policy.days_to_expiration)}>
                          {formatDate(policy.expiration_date)}
                        </Badge>
                      </td>
                      <td className="table__muted nowrap">
                        {policy.annual_premium
                          ? `${policy.annual_premium.toFixed(2)} €`
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel title="Tasks" hint={`${openTasks.length} open`} flush>
          {data.tasks.length === 0 ? (
            <EmptyState title="No tasks" />
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Task</th>
                    <th>Team</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Due</th>
                  </tr>
                </thead>
                <tbody>
                  {data.tasks.map((task) => (
                    <tr key={task.id}>
                      <td className="table__primary">{task.title}</td>
                      <td className="table__muted">{humanise(task.assigned_team)}</td>
                      <td>
                        <Badge tone={urgencyTone[task.priority]}>{task.priority}</Badge>
                      </td>
                      <td className="table__muted">{humanise(task.status)}</td>
                      <td className="table__muted nowrap">{formatDate(task.due_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Conversation history" hint={countLabel(data.conversations.length, 'thread')} flush>
        {data.conversations.length === 0 ? (
          <EmptyState title="No conversations" />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Subject</th>
                  <th>Channel</th>
                  <th>Intent</th>
                  <th>Urgency</th>
                  <th>Status</th>
                  <th>Opened</th>
                </tr>
              </thead>
              <tbody>
                {data.conversations.map((conversation) => (
                  <tr
                    key={conversation.id}
                    className="is-clickable"
                    onClick={() => navigate(`/inbox/${conversation.id}`)}
                  >
                    <td className="table__primary">{conversation.subject}</td>
                    <td className="nowrap">
                      {channelIcon(conversation.channel)} {humanise(conversation.channel)}
                    </td>
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
                      {formatDate(conversation.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel
        title="AI case history"
        hint="every analysis produced for this customer"
        flush
      >
        {data.ai_case_history.length === 0 ? (
          <EmptyState
            title="No AI analyses yet"
            hint="Open a conversation and run the pipeline."
          />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Analysis</th>
                  <th>Intent</th>
                  <th>Type</th>
                  <th>Urgency</th>
                  <th>Confidence</th>
                  <th>Action</th>
                  <th>Review</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {data.ai_case_history.map((item) => (
                  <tr key={item.id}>
                    <td className="mono">#{item.id}</td>
                    <td>{humanise(item.intent)}</td>
                    <td className="table__muted">{humanise(item.insurance_type)}</td>
                    <td>
                      <Badge tone={urgencyTone[item.urgency]}>{item.urgency}</Badge>
                    </td>
                    <td className="table__muted">{percent(item.confidence, 0)}</td>
                    <td className="table__muted">{humanise(item.recommended_action)}</td>
                    <td>
                      {item.reviewed ? (
                        <Badge tone="success">{humanise(item.reviewer_action ?? '')}</Badge>
                      ) : item.human_review_required ? (
                        <Badge tone="warning">Pending</Badge>
                      ) : (
                        <Badge tone="neutral">Not required</Badge>
                      )}
                    </td>
                    <td className="table__muted nowrap">{formatDateTime(item.created_at)}</td>
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
