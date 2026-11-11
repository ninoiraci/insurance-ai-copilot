/**
 * Evaluation dashboard.
 *
 * Runs the labelled dataset through the *same* pipeline the product uses and
 * shows accuracy, safety recall and per-case failures. The failure table is
 * the point: it is where a reviewer sees what the system actually gets wrong.
 */

import { useState } from 'react';
import { api } from '../api/client';
import { useApi, useMutation } from '../hooks/useApi';
import {
  Badge,
  EmptyState,
  ErrorState,
  Loading,
  Metric,
  Panel,
} from '../components/ui';
import type { EvaluationRun } from '../types/api';
import { DISPLAY_LOCALE, countLabel, formatDateTime, humanise, percent } from '../utils/format';

export function EvaluationsPage() {
  const { data, loading, error, refetch } = useApi(() => api.evaluations(), []);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showOnlyFailures, setShowOnlyFailures] = useState(true);

  const runEvaluation = useMutation((label: string) => api.runEvaluation(label));

  const trigger = async () => {
    const result = await runEvaluation.run(
      `manual run ${new Date().toLocaleString(DISPLAY_LOCALE)}`,
    );
    if (result) {
      setSelectedId(result.id);
      refetch();
    }
  };

  // The list endpoint returns runs without their per-case results (only
  // `latest` carries them), so selecting an older run has to fetch its detail.
  // Rendering the summary row alone silently produced an empty results table.
  const needsDetail = selectedId !== null && selectedId !== data?.latest?.id;
  const detail = useApi(
    () => (needsDetail ? api.evaluationRun(selectedId!) : Promise.resolve(null)),
    [selectedId, needsDetail],
  );

  const selected: EvaluationRun | null = needsDetail
    ? detail.data
    : data?.latest ?? null;

  return (
    <div className="page stack">
      <div className="page__header">
        <div>
          <h1>Evaluation</h1>
          <p className="page__subtitle">
            A labelled dataset of synthetic messages covering every intent, plus ambiguous,
            incomplete, noisy and adversarial cases. Each case runs through the full
            pipeline — classification, deterministic rules and the action engine — because
            that is what ships.
          </p>
        </div>
        <div className="row">
          <button
            type="button"
            className="btn btn--primary"
            onClick={trigger}
            disabled={runEvaluation.pending}
          >
            {runEvaluation.pending ? (
              <><span className="spinner" /> Running evaluation…</>
            ) : (
              'Run evaluation'
            )}
          </button>
        </div>
      </div>

      {runEvaluation.error && <ErrorState message={runEvaluation.error} />}
      {loading && <Loading />}
      {error && !loading && <ErrorState message={error} onRetry={refetch} />}

      {data && !loading && (
        <>
          <div className="callout callout--info">
            Dataset: <strong>{data.dataset_size} labelled cases</strong>. Cases are evaluated
            without customer context, which isolates message understanding from
            customer-state effects; context-dependent behaviour is covered by the backend
            unit tests.
          </div>

          {needsDetail && detail.loading ? (
            <Loading label="Loading run…" />
          ) : detail.error ? (
            <ErrorState message={detail.error} onRetry={detail.refetch} />
          ) : !selected ? (
            <EmptyState
              title="No evaluation runs yet"
              hint="Run the suite to produce accuracy, safety and latency metrics."
            />
          ) : (
            <RunDetail
              run={selected}
              showOnlyFailures={showOnlyFailures}
              onToggleFailures={() => setShowOnlyFailures((value) => !value)}
            />
          )}

          {data.items.length > 0 && (
            <Panel title="Run history" hint={countLabel(data.count, 'run')} flush>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Run</th>
                      <th>Label</th>
                      <th>Model</th>
                      <th>Cases</th>
                      <th>Intent</th>
                      <th>Action</th>
                      <th>Review recall</th>
                      <th>Duration</th>
                      <th>When</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((run) => (
                      <tr
                        key={run.id}
                        className="is-clickable"
                        onClick={() => setSelectedId(run.id)}
                        style={
                          run.id === selected?.id
                            ? { background: 'var(--accent-soft)' }
                            : undefined
                        }
                      >
                        <td className="mono">#{run.id}</td>
                        <td className="table__primary">{run.label}</td>
                        <td className="mono text-xs">
                          {run.model_name}
                          {run.demo_mode && ' (demo)'}
                        </td>
                        <td>{run.case_count}</td>
                        <td>{percent(run.metrics.intent_accuracy, 1)}</td>
                        <td>{percent(run.metrics.action_accuracy, 1)}</td>
                        <td>{percent(run.metrics.human_review_recall_on_risky, 1)}</td>
                        <td className="table__muted">{(run.duration_ms / 1000).toFixed(1)}s</td>
                        <td className="table__muted nowrap">
                          {formatDateTime(run.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}
        </>
      )}
    </div>
  );
}

function RunDetail({
  run,
  showOnlyFailures,
  onToggleFailures,
}: {
  run: EvaluationRun;
  showOnlyFailures: boolean;
  onToggleFailures: () => void;
}) {
  const { metrics } = run;
  const results = run.results ?? [];

  const isFailure = (correctness: Record<string, boolean | number>) =>
    !correctness.intent ||
    !correctness.urgency ||
    !correctness.insurance_type ||
    !correctness.action ||
    !correctness.human_review;

  const visible = showOnlyFailures
    ? results.filter((result) => isFailure(result.correctness))
    : results;

  return (
    <>
      <Panel
        title={`Run #${run.id} — ${run.label}`}
        hint={`${run.case_count} cases · ${run.model_name}${run.demo_mode ? ' (demo mode)' : ''}`}
      >
        <div className="metric-grid">
          <Metric
            label="Intent accuracy"
            value={percent(metrics.intent_accuracy, 1)}
            hint="exact match on 12 labels"
          />
          <Metric
            label="Urgency accuracy"
            value={percent(metrics.urgency_accuracy, 1)}
            hint="after deterministic rules"
          />
          <Metric
            label="Insurance type"
            value={percent(metrics.insurance_type_accuracy, 1)}
            hint="product classification"
          />
          <Metric
            label="Action accuracy"
            value={percent(metrics.action_accuracy, 1)}
            hint="next-best-action decision"
          />
          <Metric
            label="Schema validation"
            value={percent(metrics.schema_validation_rate, 1)}
            hint="outputs that validated without fallback"
          />
          <Metric
            label="Entity F1"
            value={metrics.entity_extraction.f1.toFixed(3)}
            hint={`P ${metrics.entity_extraction.precision.toFixed(2)} · R ${metrics.entity_extraction.recall.toFixed(2)}`}
          />
          <Metric
            label="Review recall (risky)"
            value={percent(metrics.human_review_recall_on_risky, 1)}
            hint={`${metrics.risky_cases} cases that must reach a human`}
          />
          <Metric
            label="Review false alarms"
            value={percent(metrics.human_review_false_alarm_rate, 1)}
            hint="safe cases flagged unnecessarily"
          />
          <Metric
            label="Avg latency"
            value={`${metrics.avg_latency_ms} ms`}
            hint={`p95 ${metrics.p95_latency_ms} ms`}
          />
          <Metric
            label="Tokens"
            value={
              metrics.total_input_tokens + metrics.total_output_tokens === 0
                ? 'n/a'
                : `${metrics.total_input_tokens + metrics.total_output_tokens}`
            }
            hint={
              run.demo_mode
                ? 'demo mode makes no API calls'
                : `${metrics.total_input_tokens} in / ${metrics.total_output_tokens} out`
            }
          />
        </div>

        <div className="callout callout--warning mt-md">
          <strong>Review recall is the metric that matters most.</strong> A missed risky case
          means a draft could reach a customer without a human reading it. Accuracy numbers
          measure usefulness; this one measures safety.
        </div>
      </Panel>

      <Panel
        title="Per-case results"
        hint={`${visible.length} of ${results.length} shown`}
        actions={
          <button type="button" className="btn btn--sm" onClick={onToggleFailures}>
            {showOnlyFailures ? 'Show all cases' : 'Show only failures'}
          </button>
        }
        flush
      >
        {visible.length === 0 ? (
          <EmptyState
            title={showOnlyFailures ? 'No failures in this run' : 'No results'}
            hint={showOnlyFailures ? 'Every case matched its expected labels.' : undefined}
          />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Intent (exp → got)</th>
                  <th>Urgency</th>
                  <th>Action</th>
                  <th>Review</th>
                  <th>Entities</th>
                  <th>Latency</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((result) => (
                  <tr key={result.id}>
                    <td className="mono nowrap">
                      {result.case_key}
                      {result.error && <Badge tone="danger">error</Badge>}
                    </td>
                    <td>
                      <Cell
                        ok={Boolean(result.correctness.intent)}
                        expected={String(result.expected.intent ?? '')}
                        actual={String(result.predicted.intent ?? '')}
                      />
                    </td>
                    <td>
                      <Cell
                        ok={Boolean(result.correctness.urgency)}
                        expected={String(result.expected.urgency ?? '')}
                        actual={String(result.predicted.urgency ?? '')}
                      />
                    </td>
                    <td>
                      <Cell
                        ok={Boolean(result.correctness.action)}
                        expected={humanise(String(result.expected.action ?? ''))}
                        actual={humanise(String(result.predicted.action ?? ''))}
                      />
                    </td>
                    <td>
                      {result.correctness.human_review ? (
                        <Badge tone="success">ok</Badge>
                      ) : (
                        <Badge tone="danger">
                          {result.expected.expects_human_review ? 'missed' : 'false alarm'}
                        </Badge>
                      )}
                    </td>
                    <td className="table__muted nowrap">
                      {String(result.correctness.entities_matched ?? 0)}/
                      {String(result.correctness.entities_expected ?? 0)}
                    </td>
                    <td className="table__muted">{result.latency_ms} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}

function Cell({
  ok,
  expected,
  actual,
}: {
  ok: boolean;
  expected: string;
  actual: string;
}) {
  if (ok) {
    return <span className="text-sm">{humanise(actual)}</span>;
  }
  return (
    <span className="text-sm">
      <span className="muted">{humanise(expected)}</span>{' '}
      <span style={{ color: 'var(--danger)' }}>→ {humanise(actual)}</span>
    </span>
  );
}
