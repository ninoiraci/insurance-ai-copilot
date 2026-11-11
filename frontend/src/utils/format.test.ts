import { describe, expect, it } from 'vitest';

import { countLabel, formatDate, formatDateTime } from './format';

describe('countLabel', () => {
  it('uses the singular for exactly one item', () => {
    expect(countLabel(1, 'message')).toBe('1 message');
  });

  it('uses the plural otherwise, including zero', () => {
    expect(countLabel(0, 'message')).toBe('0 messages');
    expect(countLabel(3, 'entry', 'entries')).toBe('3 entries');
  });
});

describe('date formatting', () => {
  it('uses English month names whatever the browser locale', () => {
    expect(formatDate('2027-06-19')).toMatch(/Jun/);
    expect(formatDateTime('2026-10-11T09:30:00')).toMatch(/Oct/);
  });
});
