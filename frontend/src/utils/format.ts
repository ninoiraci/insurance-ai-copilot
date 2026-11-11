/** Shared formatting and label helpers. */

import type { Urgency } from '../types/api';

export type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

// The interface is in English, so dates are too, whatever the browser locale.
export const DISPLAY_LOCALE = 'en-GB';

// Labels whose natural casing the generic rule would get wrong.
const LABEL_OVERRIDES: Record<string, string> = {
  WHATSAPP: 'WhatsApp',
  AI_PROCESSED: 'AI processed',
  GDPR: 'GDPR',
  AI_ANALYSIS_CREATED: 'AI analysis created',
  AI_ANALYSIS_FAILED: 'AI analysis failed',
  AI_OUTPUT_VALIDATION_FAILED: 'AI output validation failed',
};

/**
 * Turn an enum constant into a sentence-cased label.
 * CLAIM -> "Claim", REQUEST_DOCUMENTS -> "Request documents".
 */
export function humanise(value: string | null | undefined): string {
  if (!value) return '—';
  const upper = value.toUpperCase();
  if (LABEL_OVERRIDES[upper]) return LABEL_OVERRIDES[upper];

  const words = value.split('_').join(' ').toLowerCase().trim();
  if (!words) return '—';
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export const urgencyTone: Record<Urgency, Tone> = {
  LOW: 'neutral',
  MEDIUM: 'info',
  HIGH: 'warning',
  CRITICAL: 'danger',
};

/** Covers conversation, policy and task statuses — they share the badge. */
export function statusTone(status: string): Tone {
  switch (status) {
    case 'PENDING_REVIEW':
    case 'PENDING_RENEWAL':
      return 'warning';
    case 'ESCALATED':
    case 'LAPSED':
    case 'CANCELLED':
      return 'danger';
    case 'RESOLVED':
    case 'ACTIVE':
    case 'DONE':
      return 'success';
    case 'AI_PROCESSED':
    case 'AWAITING_CUSTOMER':
    case 'IN_PROGRESS':
      return 'info';
    default:
      return 'neutral';
  }
}

export function channelIcon(channel: string): string {
  switch (channel) {
    case 'WHATSAPP':
      return '💬';
    case 'EMAIL':
      return '✉️';
    case 'PHONE_CALL':
      return '📞';
    default:
      return '•';
  }
}

/** Confidence colour: red below the routing floor, amber below the threshold. */
export function confidenceColor(confidence: number): string {
  if (confidence >= 0.75) return 'var(--success)';
  if (confidence >= 0.45) return 'var(--warning)';
  return 'var(--danger)';
}

/** "1 message", "3 messages". */
export function countLabel(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso.endsWith('Z') ? iso : `${iso}Z`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(DISPLAY_LOCALE, {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(DISPLAY_LOCALE, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso.endsWith('Z') ? iso : `${iso}Z`);
  if (Number.isNaN(date.getTime())) return iso;

  const minutes = Math.round((Date.now() - date.getTime()) / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return days < 30 ? `${days}d ago` : formatDate(iso);
}

export function percent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return '—';
  return `${(value * 100).toFixed(digits)}%`;
}

/** Render an extracted entity value for display without losing information. */
export function formatEntityValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (Array.isArray(value)) return value.map(formatEntityValue).join(', ');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

/** Days-to-expiry colouring, matching the backend's renewal thresholds. */
export function expiryTone(days: number): Tone {
  if (days < 0) return 'danger';
  if (days <= 7) return 'danger';
  if (days <= 30) return 'warning';
  return 'neutral';
}
