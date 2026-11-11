/** Unified multi-channel inbox with server-side and AI-label filtering. */

import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type ConversationFilters } from '../api/client';
import { useApi, useDebounced } from '../hooks/useApi';
import { Badge, EmptyState, ErrorState, Loading, Panel } from '../components/ui';
import {
  channelIcon,
  humanise,
  percent,
  relativeTime,
  statusTone,
  urgencyTone,
} from '../utils/format';

const ANY = '';

export function InboxPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [channel, setChannel] = useState(ANY);
  const [intent, setIntent] = useState(ANY);
  const [urgency, setUrgency] = useState(ANY);
  const [status, setStatus] = useState(ANY);
  const [reviewOnly, setReviewOnly] = useState(false);

  const debouncedSearch = useDebounced(search);

  const filters: ConversationFilters = useMemo(
    () => ({
      search: debouncedSearch || undefined,
      channel: channel || undefined,
      intent: intent || undefined,
      urgency: urgency || undefined,
      status: status || undefined,
      review_required: reviewOnly || undefined,
    }),
    [debouncedSearch, channel, intent, urgency, status, reviewOnly],
  );

  const { data, loading, error, refetch } = useApi(
    () => api.conversations(filters),
    [filters],
  );

  const hasFilters = Boolean(
    debouncedSearch || channel || intent || urgency || status || reviewOnly,
  );

  const clearFilters = () => {
    setSearch('');
    setChannel(ANY);
    setIntent(ANY);
    setUrgency(ANY);
    setStatus(ANY);
    setReviewOnly(false);
  };

  const options = data?.filters;

  return (
    <div className="page stack">
      <div className="page__header">
        <div>
          <h1>Unified inbox</h1>
          <p className="page__subtitle">
            WhatsApp, email and call transcripts in one queue. Intent, urgency and routing
            labels come from the AI pipeline; conversations without labels have not been
            analysed yet.
          </p>
        </div>
      </div>

      <Panel title="Filters">
        <div className="filters">
          <div className="field field--grow">
            <label className="field__label" htmlFor="inbox-search">
              Search
            </label>
            <input
              id="inbox-search"
              className="input"
              placeholder="Customer, subject or reference…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>

          <div className="field">
            <label className="field__label" htmlFor="inbox-channel">Channel</label>
            <select
              id="inbox-channel"
              className="select"
              value={channel}
              onChange={(event) => setChannel(event.target.value)}
            >
              <option value={ANY}>All channels</option>
              {options?.channels.map((value) => (
                <option key={value} value={value}>{humanise(value)}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="field__label" htmlFor="inbox-intent">Intent</label>
            <select
              id="inbox-intent"
              className="select"
              value={intent}
              onChange={(event) => setIntent(event.target.value)}
            >
              <option value={ANY}>All intents</option>
              {options?.intents.map((value) => (
                <option key={value} value={value}>{humanise(value)}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="field__label" htmlFor="inbox-urgency">Urgency</label>
            <select
              id="inbox-urgency"
              className="select"
              value={urgency}
              onChange={(event) => setUrgency(event.target.value)}
            >
              <option value={ANY}>All urgencies</option>
              {options?.urgencies.map((value) => (
                <option key={value} value={value}>{humanise(value)}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="field__label" htmlFor="inbox-status">Status</label>
            <select
              id="inbox-status"
              className="select"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value={ANY}>All statuses</option>
              {options?.statuses.map((value) => (
                <option key={value} value={value}>{humanise(value)}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="field__label">Review</label>
            <label className="row text-sm" style={{ height: 33 }}>
              <input
                type="checkbox"
                checked={reviewOnly}
                onChange={(event) => setReviewOnly(event.target.checked)}
              />
              Needs human review
            </label>
          </div>

          {hasFilters && (
            <button type="button" className="btn btn--sm" onClick={clearFilters}>
              Clear
            </button>
          )}
        </div>
      </Panel>

      <Panel
        title="Conversations"
        hint={data ? `${data.count} shown` : undefined}
        actions={
          <button type="button" className="btn btn--sm" onClick={refetch}>
            Refresh
          </button>
        }
        flush
      >
        {loading && <Loading label="Loading conversations…" />}
        {error && !loading && (
          <div style={{ padding: 16 }}>
            <ErrorState message={error} onRetry={refetch} />
          </div>
        )}
        {data && !loading && data.items.length === 0 && (
          <EmptyState
            title="No conversations match these filters"
            hint={hasFilters ? 'Try clearing some filters.' : 'Seed the demo data first.'}
          />
        )}

        {data && !loading && data.items.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Customer</th>
                  <th>Channel</th>
                  <th>Subject / last message</th>
                  <th>Intent</th>
                  <th>Urgency</th>
                  <th>Confidence</th>
                  <th>Team</th>
                  <th>Status</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((conversation) => {
                  const analysis = conversation.latest_analysis;
                  return (
                    <tr
                      key={conversation.id}
                      className="is-clickable"
                      onClick={() => navigate(`/inbox/${conversation.id}`)}
                    >
                      <td className="table__primary nowrap">
                        {conversation.customer_name}
                        {conversation.reference && (
                          <div className="table__muted">{conversation.reference}</div>
                        )}
                      </td>
                      <td className="nowrap">
                        {channelIcon(conversation.channel)} {humanise(conversation.channel)}
                      </td>
                      <td>
                        <div className="table__primary">{conversation.subject}</div>
                        {conversation.preview && (
                          <div className="table__preview table__muted">
                            {conversation.preview}
                          </div>
                        )}
                      </td>
                      <td>
                        {analysis ? (
                          <Badge tone="accent">{humanise(analysis.intent)}</Badge>
                        ) : (
                          <span className="table__muted">Not analysed</span>
                        )}
                      </td>
                      <td>
                        {analysis ? (
                          <Badge tone={urgencyTone[analysis.urgency]}>{analysis.urgency}</Badge>
                        ) : (
                          <span className="table__muted">—</span>
                        )}
                      </td>
                      <td className="table__muted nowrap">
                        {analysis ? percent(analysis.confidence, 0) : '—'}
                      </td>
                      <td className="table__muted nowrap">
                        {humanise(conversation.assigned_team)}
                      </td>
                      <td>
                        {analysis?.human_review_required && !analysis.reviewed ? (
                          <Badge tone="warning">Human review</Badge>
                        ) : analysis?.reviewed ? (
                          <Badge tone="success">
                            {humanise(analysis.reviewer_action ?? 'Reviewed')}
                          </Badge>
                        ) : (
                          <Badge tone={statusTone(conversation.status)}>
                            {humanise(conversation.status)}
                          </Badge>
                        )}
                      </td>
                      <td className="table__muted nowrap">
                        {relativeTime(conversation.updated_at)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
