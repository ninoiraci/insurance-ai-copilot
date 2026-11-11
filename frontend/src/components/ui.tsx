/** Small presentational primitives shared across pages. */

import { Fragment, type ReactNode } from 'react';
import { confidenceColor, percent, type Tone } from '../utils/format';

export function Badge({
  children,
  tone = 'neutral',
  title,
}: {
  children: ReactNode;
  tone?: Tone;
  title?: string;
}) {
  return (
    <span className={`badge badge--${tone}`} title={title}>
      {children}
    </span>
  );
}

export function Panel({
  title,
  hint,
  actions,
  children,
  flush = false,
}: {
  title?: ReactNode;
  hint?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  flush?: boolean;
}) {
  return (
    <section className="panel">
      {(title || actions) && (
        <header className="panel__header">
          <div className="panel__title">
            {title}
            {hint && <span className="panel__hint">{hint}</span>}
          </div>
          {actions}
        </header>
      )}
      <div className={flush ? 'panel__body panel__body--flush' : 'panel__body'}>{children}</div>
    </section>
  );
}

export function Stat({
  label,
  value,
  hint,
  variant,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  variant?: 'danger' | 'warning' | 'success';
}) {
  return (
    <div className="stat">
      <div className="stat__label">{label}</div>
      <div className={variant ? `stat__value stat__value--${variant}` : 'stat__value'}>
        {value}
      </div>
      {hint && <div className="stat__hint">{hint}</div>}
    </div>
  );
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="state" role="status">
      <span className="spinner" /> <span style={{ marginLeft: 8 }}>{label}</span>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state state--error" role="alert">
      <div className="state__title">Something went wrong</div>
      <div>{message}</div>
      {onRetry && (
        <button type="button" className="btn btn--sm mt-sm" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: ReactNode }) {
  return (
    <div className="state">
      <div className="state__title">{title}</div>
      {hint && <div>{hint}</div>}
    </div>
  );
}

export function ConfidenceBar({ value }: { value: number }) {
  const clamped = Math.max(0, Math.min(1, value));
  return (
    <div className="confidence">
      <div className="confidence__track">
        <div
          className="confidence__fill"
          style={{ width: `${clamped * 100}%`, background: confidenceColor(clamped) }}
        />
      </div>
      <span className="confidence__value" style={{ color: confidenceColor(clamped) }}>
        {percent(clamped, 0)}
      </span>
    </div>
  );
}

export function BarList({
  items,
  emptyLabel = 'No data yet',
}: {
  items: Array<{ label: string; count: number }>;
  emptyLabel?: string;
}) {
  const max = Math.max(1, ...items.map((item) => item.count));
  const visible = items.filter((item) => item.count > 0);

  if (visible.length === 0) return <EmptyState title={emptyLabel} />;

  return (
    <div className="bars">
      {visible.map((item) => (
        <div className="bar-row" key={item.label}>
          <span className="bar-row__label" title={item.label}>
            {item.label}
          </span>
          <span className="bar-row__track">
            <span
              className="bar-row__fill"
              style={{ width: `${(item.count / max) * 100}%` }}
            />
          </span>
          <span className="bar-row__value">{item.count}</span>
        </div>
      ))}
    </div>
  );
}

export function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
}) {
  return (
    <div className="metric">
      <div className="metric__label">{label}</div>
      <div className="metric__value">{value}</div>
      {hint && <div className="metric__hint">{hint}</div>}
    </div>
  );
}

export function KeyValue({ rows }: { rows: Array<[string, ReactNode]> }) {
  return (
    <div className="kv">
      {rows.map(([key, value]) => (
        <Fragment key={key}>
          <span className="kv__key">{key}</span>
          <span className="kv__value">{value}</span>
        </Fragment>
      ))}
    </div>
  );
}
