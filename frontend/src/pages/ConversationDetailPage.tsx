/**
 * The main demo screen: thread · customer 360 · AI copilot.
 *
 * State lives here and flows down; the three columns are presentational. After
 * an analysis or a review the whole conversation is refetched rather than
 * patched locally — the backend is the source of truth for status transitions,
 * task creation and audit entries.
 */

import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useApi, useMutation } from '../hooks/useApi';
import { CopilotPanel } from '../components/CopilotPanel';
import { ConversationThread } from '../components/ConversationThread';
import { Customer360 } from '../components/Customer360';
import { Badge, ErrorState, Loading, Panel } from '../components/ui';
import type { ReviewerAction } from '../types/api';
import { channelIcon, countLabel, formatDateTime, humanise, statusTone } from '../utils/format';

export function ConversationDetailPage() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const id = Number(conversationId);

  const { data, loading, error, refetch } = useApi(() => api.conversation(id), [id]);

  const analyse = useMutation((force: boolean) => api.analyze(id, force));
  const review = useMutation(
    (analysisId: number, action: ReviewerAction, finalResponse: string, notes: string) =>
      api.review(analysisId, {
        action,
        // Only send the edited text when it is actually an edit; the backend
        // rejects EDIT_AND_APPROVE without a body.
        final_response: action === 'EDIT_AND_APPROVE' ? finalResponse : undefined,
        reviewer_notes: notes || undefined,
        reviewer_name: 'demo.operator',
      }),
  );

  if (Number.isNaN(id)) {
    return <div className="page"><ErrorState message="Invalid conversation id." /></div>;
  }
  if (loading) return <div className="page"><Loading label="Loading conversation…" /></div>;
  if (error) return <div className="page"><ErrorState message={error} onRetry={refetch} /></div>;
  if (!data) return null;

  const analysis = data.analyses.at(-1) ?? null;

  const handleAnalyse = async (force: boolean) => {
    const result = await analyse.run(force);
    if (result) refetch();
  };

  const handleReview = async (
    action: ReviewerAction,
    finalResponse: string,
    notes: string,
  ) => {
    if (!analysis) return;
    const result = await review.run(analysis.id, action, finalResponse, notes);
    if (result) refetch();
  };

  return (
    <div className="page stack">
      <div className="page__header">
        <div>
          <div className="row text-sm muted" style={{ marginBottom: 4 }}>
            <Link to="/inbox">← Inbox</Link>
            {data.reference && <span className="mono">{data.reference}</span>}
          </div>
          <h1>{data.subject}</h1>
          <p className="page__subtitle">
            {channelIcon(data.channel)} {humanise(data.channel)} ·{' '}
            <button
              type="button"
              className="btn btn--sm"
              style={{ padding: '0 4px', border: 'none', background: 'none', color: 'var(--accent)' }}
              onClick={() => navigate(`/customers/${data.customer_id}`)}
            >
              {data.customer_name}
            </button>{' '}
            · opened {formatDateTime(data.created_at)}
          </p>
        </div>
        <div className="row">
          <Badge tone={statusTone(data.status)}>{humanise(data.status)}</Badge>
          <Badge tone="neutral">{humanise(data.assigned_team)}</Badge>
        </div>
      </div>

      <div className="workspace">
        <Panel
          title="Conversation"
          hint={countLabel(data.messages.length, 'message')}
          flush
        >
          <ConversationThread
            messages={data.messages}
            analysedMessageId={analysis?.message_id}
          />
        </Panel>

        <Panel title="Customer 360" hint="context given to the AI" flush>
          <Customer360
            customer={data.customer}
            context={data.ai_context}
            tasks={data.tasks}
          />
        </Panel>

        <Panel
          title="AI Copilot"
          hint={analysis ? `analysis #${analysis.id}` : 'not run yet'}
          flush
        >
          <CopilotPanel
            analysis={analysis}
            analysing={analyse.pending}
            analyseError={analyse.error}
            reviewError={review.error}
            reviewPending={review.pending}
            onAnalyse={handleAnalyse}
            onReview={handleReview}
          />
        </Panel>
      </div>

      {data.analyses.length > 1 && (
        <Panel title="Analysis history" hint={countLabel(data.analyses.length, 'run')} flush>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Intent</th>
                  <th>Urgency</th>
                  <th>Action</th>
                  <th>Model</th>
                  <th>Latency</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {data.analyses.map((item) => (
                  <tr key={item.id}>
                    <td className="mono">{item.id}</td>
                    <td>{humanise(item.intent)}</td>
                    <td>{item.urgency}</td>
                    <td>{humanise(item.recommended_action)}</td>
                    <td className="mono text-xs">{item.metadata.model_name}</td>
                    <td className="table__muted">{item.metadata.processing_latency_ms} ms</td>
                    <td className="table__muted">{formatDateTime(item.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  );
}
