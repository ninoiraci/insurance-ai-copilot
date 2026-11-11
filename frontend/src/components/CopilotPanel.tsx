/**
 * Right column: the AI Copilot.
 *
 * Everything the system decided, why it decided it, what it was allowed to
 * read, and the three human actions. The technical metadata is collapsed by
 * default so operators see the decision and reviewers can still audit it.
 */

import { Fragment, useState } from 'react';
import type { Analysis, ReviewerAction } from '../types/api';
import {
  confidenceColor,
  formatDateTime,
  formatEntityValue,
  humanise,
  percent,
  urgencyTone,
} from '../utils/format';
import { Badge, ConfidenceBar, EmptyState } from './ui';

interface Props {
  analysis: Analysis | null;
  analysing: boolean;
  analyseError: string | null;
  reviewError: string | null;
  reviewPending: boolean;
  onAnalyse: (force: boolean) => void;
  onReview: (action: ReviewerAction, finalResponse: string, notes: string) => void;
}

export function CopilotPanel({
  analysis,
  analysing,
  analyseError,
  reviewError,
  reviewPending,
  onAnalyse,
  onReview,
}: Props) {
  if (!analysis) {
    return (
      <div className="copilot__section">
        <EmptyState
          title="Not analysed yet"
          hint="Run the AI pipeline to classify this conversation, retrieve the relevant procedure and draft a reply."
        />
        {analyseError && (
          <div className="callout callout--danger mt-sm">{analyseError}</div>
        )}
        <button
          type="button"
          className="btn btn--primary btn--block mt-md"
          onClick={() => onAnalyse(false)}
          disabled={analysing}
        >
          {analysing ? <><span className="spinner" /> Analysing…</> : 'Run AI analysis'}
        </button>
      </div>
    );
  }

  return (
    <>
      <ClassificationSection analysis={analysis} />
      <ExtractionSection analysis={analysis} />
      <RulesSection analysis={analysis} />
      <SourcesSection analysis={analysis} />
      <ActionSection analysis={analysis} />
      {/*
        Keyed by analysis id: the draft lives in local state, so without a
        remount "Re-run analysis" would leave the previous analysis's text in
        the editor while the rest of the panel showed the new one.
      */}
      <ReviewSection
        key={analysis.id}
        analysis={analysis}
        reviewError={reviewError}
        reviewPending={reviewPending}
        onReview={onReview}
      />
      <TechnicalSection analysis={analysis} />

      <div className="copilot__section">
        {analyseError && <div className="callout callout--danger mt-sm">{analyseError}</div>}
        <button
          type="button"
          className="btn btn--sm btn--block"
          onClick={() => onAnalyse(true)}
          disabled={analysing}
          title="Re-runs the whole pipeline and stores a second, separately audited analysis"
        >
          {analysing ? <><span className="spinner" /> Re-analysing…</> : 'Re-run analysis'}
        </button>
      </div>
    </>
  );
}

function ClassificationSection({ analysis }: { analysis: Analysis }) {
  return (
    <section className="copilot__section">
      <div className="copilot__section-title">
        Classification
        {analysis.metadata.demo_mode && <Badge tone="warning">Demo AI</Badge>}
      </div>

      <div className="chips" style={{ marginBottom: 10 }}>
        <Badge tone="accent">{humanise(analysis.intent)}</Badge>
        <Badge tone="neutral">{humanise(analysis.insurance_type)}</Badge>
        <Badge tone={urgencyTone[analysis.urgency]}>{analysis.urgency}</Badge>
        {analysis.grounded ? (
          <Badge tone="success">Grounded</Badge>
        ) : (
          <Badge tone="warning">Not grounded</Badge>
        )}
      </div>

      <div className="field" style={{ marginBottom: 10 }}>
        <span className="field__label">Confidence</span>
        <ConfidenceBar value={analysis.confidence} />
      </div>

      <p className="text-sm secondary">{analysis.summary}</p>
    </section>
  );
}

function ExtractionSection({ analysis }: { analysis: Analysis }) {
  const entities = Object.entries(analysis.extracted_entities);

  return (
    <section className="copilot__section">
      <div className="copilot__section-title">Extracted information</div>
      {entities.length === 0 ? (
        <p className="text-sm muted">No structured facts could be extracted.</p>
      ) : (
        <div className="kv">
          {entities.map(([key, value]) => (
            <Fragment key={key}>
              <span className="kv__key">{humanise(key)}</span>
              <span className="kv__value mono">{formatEntityValue(value)}</span>
            </Fragment>
          ))}
        </div>
      )}

      <div className="copilot__section-title" style={{ marginTop: 14 }}>
        Missing information
      </div>
      {analysis.missing_information.length === 0 ? (
        <p className="text-sm muted">Nothing outstanding — the case can proceed.</p>
      ) : (
        <ul className="list-plain">
          {analysis.missing_information.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

function RulesSection({ analysis }: { analysis: Analysis }) {
  if (analysis.rule_overrides.length === 0 && analysis.safety_flags.length === 0) return null;

  return (
    <section className="copilot__section">
      <div className="copilot__section-title">Deterministic rules applied</div>

      {analysis.safety_flags.map((flag) => (
        <div className="callout callout--danger" key={flag} style={{ marginBottom: 8 }}>
          <strong>{humanise(flag)}</strong>
          <div className="mt-sm">
            The customer text contains instructions aimed at the AI system. It was treated as
            data, retrieval was skipped and the case was routed to compliance. No customer
            data was exposed.
          </div>
        </div>
      ))}

      {analysis.rule_overrides.map((override) => (
        <div className="callout callout--warning" key={override.rule} style={{ marginBottom: 8 }}>
          <strong>
            {humanise(override.rule)}: {override.from} → {override.to}
          </strong>
          <div className="mt-sm">{override.reason}</div>
        </div>
      ))}
    </section>
  );
}

function SourcesSection({ analysis }: { analysis: Analysis }) {
  const [expanded, setExpanded] = useState<number | null>(null);

  return (
    <section className="copilot__section">
      <div className="copilot__section-title">
        Retrieved knowledge
        <span className="panel__hint">{analysis.retrieved_sources.length} chunks</span>
      </div>

      {analysis.retrieved_sources.length === 0 ? (
        <div className="callout callout--info">
          No internal documentation was retrieved for this case, so the draft below is a
          holding reply only. The system does not answer procedural questions from memory.
        </div>
      ) : (
        analysis.retrieved_sources.map((source) => (
          <div className="source" key={source.chunk_id}>
            <div className="source__head">
              <span className="source__title">{source.citation}</span>
              <span className="source__score">{source.similarity.toFixed(3)}</span>
            </div>
            <div
              className={
                expanded === source.chunk_id
                  ? 'source__excerpt source__excerpt--open'
                  : 'source__excerpt'
              }
            >
              {source.content}
            </div>
            <button
              type="button"
              className="btn btn--sm mt-sm"
              onClick={() =>
                setExpanded(expanded === source.chunk_id ? null : source.chunk_id)
              }
            >
              {expanded === source.chunk_id ? 'Show less' : 'Show full chunk'}
            </button>
          </div>
        ))
      )}
    </section>
  );
}

function ActionSection({ analysis }: { analysis: Analysis }) {
  return (
    <section className="copilot__section">
      <div className="copilot__section-title">Recommended next action</div>
      <div className="chips" style={{ marginBottom: 8 }}>
        <Badge tone="accent">{humanise(analysis.recommended_action)}</Badge>
        <Badge tone="neutral">{humanise(analysis.assigned_team)}</Badge>
        {analysis.follow_up_hours !== null && (
          <Badge tone="info">follow up in {analysis.follow_up_hours}h</Badge>
        )}
      </div>
      {analysis.action_reason && <p className="text-sm secondary">{analysis.action_reason}</p>}
    </section>
  );
}

function ReviewSection({
  analysis,
  reviewError,
  reviewPending,
  onReview,
}: {
  analysis: Analysis;
  reviewError: string | null;
  reviewPending: boolean;
  onReview: (action: ReviewerAction, finalResponse: string, notes: string) => void;
}) {
  const existingReview = analysis.reviews.at(-1) ?? null;
  const [draft, setDraft] = useState(analysis.suggested_response);
  const [notes, setNotes] = useState('');
  const [editing, setEditing] = useState(false);

  const edited = draft.trim() !== analysis.suggested_response.trim();

  return (
    <section className="copilot__section">
      <div className="copilot__section-title">
        Suggested customer response
        {analysis.human_review_required && !existingReview && (
          <Badge tone="warning">Human review required</Badge>
        )}
      </div>

      {analysis.review_reasons.length > 0 && !existingReview && (
        <div className="callout callout--warning" style={{ marginBottom: 10 }}>
          <strong>Why a human must review this</strong>
          <ul className="list-plain mt-sm">
            {analysis.review_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      {existingReview ? (
        <>
          <div
            className={
              existingReview.reviewer_action === 'REJECT'
                ? 'callout callout--danger'
                : 'callout callout--success'
            }
            style={{ marginBottom: 10 }}
          >
            <strong>{humanise(existingReview.reviewer_action)}</strong> by{' '}
            {existingReview.reviewer_name} · {formatDateTime(existingReview.timestamp)}
            {existingReview.simulated_send && (
              <div className="mt-sm">
                Delivery simulated only — this proof of concept never contacts a customer.
              </div>
            )}
            {existingReview.reviewer_notes && (
              <div className="mt-sm">Notes: {existingReview.reviewer_notes}</div>
            )}
          </div>

          <div className="field">
            <span className="field__label">
              {existingReview.reviewer_action === 'REJECT'
                ? 'Rejected draft'
                : 'Final response'}
            </span>
            <div className="source">
              <div className="pre-wrap text-sm">
                {existingReview.final_response ?? existingReview.original_response}
              </div>
            </div>
          </div>

          {existingReview.reviewer_action === 'EDIT_AND_APPROVE' && (
            <details className="mt-sm">
              <summary className="text-xs muted" style={{ cursor: 'pointer' }}>
                Show the original AI draft
              </summary>
              <div className="source mt-sm">
                <div className="pre-wrap text-sm muted">{existingReview.original_response}</div>
              </div>
            </details>
          )}
        </>
      ) : (
        <>
          {analysis.retrieved_sources.length > 0 && (
            <p className="text-xs muted" style={{ marginBottom: 6 }}>
              Grounded in: {analysis.retrieved_sources.map((s) => s.citation).join(' · ')}
            </p>
          )}

          {editing ? (
            <textarea
              className="textarea"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              aria-label="Edit the suggested response"
            />
          ) : (
            <div className="source">
              <div className="pre-wrap text-sm">{draft}</div>
            </div>
          )}

          {editing && (
            <div className="field mt-sm">
              <label className="field__label" htmlFor="review-notes">
                Reviewer notes (optional)
              </label>
              <input
                id="review-notes"
                className="input"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="Why did you change it?"
              />
            </div>
          )}

          {reviewError && <div className="callout callout--danger mt-sm">{reviewError}</div>}

          <div className="actions mt-md">
            <button
              type="button"
              className="btn btn--success"
              disabled={reviewPending}
              onClick={() => onReview(edited ? 'EDIT_AND_APPROVE' : 'APPROVE', draft, notes)}
            >
              {reviewPending && <span className="spinner" />}
              {edited ? 'Save & approve' : 'Approve'}
            </button>
            <button
              type="button"
              className="btn"
              disabled={reviewPending}
              onClick={() => setEditing((value) => !value)}
            >
              {editing ? 'Cancel edit' : 'Edit'}
            </button>
            <button
              type="button"
              className="btn btn--danger"
              disabled={reviewPending}
              onClick={() => onReview('REJECT', draft, notes)}
            >
              Reject
            </button>
          </div>

          <p className="text-xs muted mt-sm">
            Approving records the decision and closes the work item. No message is sent —
            delivery is simulated in this proof of concept.
          </p>
        </>
      )}
    </section>
  );
}

function TechnicalSection({ analysis }: { analysis: Analysis }) {
  const { metadata } = analysis;
  return (
    <details className="tech">
      <summary>Technical metadata</summary>
      <div className="tech__body">
        <div className="kv mono">
          <span className="kv__key">Model</span>
          <span className="kv__value">{metadata.model_name}</span>
          <span className="kv__key">Prompt version</span>
          <span className="kv__value">{metadata.prompt_version}</span>
          <span className="kv__key">Latency</span>
          <span className="kv__value">{metadata.processing_latency_ms} ms</span>
          <span className="kv__key">Confidence</span>
          <span className="kv__value" style={{ color: confidenceColor(analysis.confidence) }}>
            {percent(analysis.confidence, 1)}
          </span>
          <span className="kv__key">Validation attempts</span>
          <span className="kv__value">{metadata.validation_attempts}</span>
          <span className="kv__key">Retrieved chunks</span>
          <span className="kv__value">{metadata.retrieved_chunk_count}</span>
          <span className="kv__key">Demo mode</span>
          <span className="kv__value">{metadata.demo_mode ? 'yes (mock output)' : 'no'}</span>
          <span className="kv__key">Tokens</span>
          <span className="kv__value">
            {metadata.token_usage
              ? `${metadata.token_usage.input_tokens ?? 0} in / ${
                  metadata.token_usage.output_tokens ?? 0
                } out`
              : 'n/a'}
          </span>
          <span className="kv__key">Analysis id</span>
          <span className="kv__value">#{analysis.id}</span>
          <span className="kv__key">Created</span>
          <span className="kv__value">{formatDateTime(metadata.created_at)}</span>
        </div>
      </div>
    </details>
  );
}
