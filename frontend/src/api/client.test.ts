/** The API client's error contract, which every page depends on. */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, api } from './client';

function mockFetch(response: Partial<Response> & { json?: () => Promise<unknown> }) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({}),
    ...response,
  }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('api client', () => {
  it('returns the parsed body on success', async () => {
    mockFetch({ json: async () => ({ status: 'ok', ai_demo_mode: true }) });

    await expect(api.health()).resolves.toEqual({ status: 'ok', ai_demo_mode: true });
  });

  it('unwraps the backend error envelope', async () => {
    mockFetch({
      ok: false,
      status: 409,
      json: async () => ({
        error: { code: 'conflict', message: 'This message has already been analysed.' },
      }),
    });

    await expect(api.analyze(1)).rejects.toMatchObject({
      message: 'This message has already been analysed.',
      status: 409,
      code: 'conflict',
    });
  });

  it('reports a network failure distinctly from a server error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));

    await expect(api.dashboard()).rejects.toMatchObject({
      code: 'network_error',
      status: 0,
    });
  });

  it('falls back to a generic message when the body is not JSON', async () => {
    mockFetch({ ok: false, status: 500, json: async () => { throw new Error('nope'); } });

    await expect(api.dashboard()).rejects.toBeInstanceOf(ApiError);
  });

  it('serialises filters into the query string, omitting empties', async () => {
    const spy = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) });
    vi.stubGlobal('fetch', spy);

    await api.conversations({ search: 'Carlos', channel: 'EMAIL', intent: undefined });

    expect(spy.mock.calls[0][0]).toBe('/api/conversations?search=Carlos&channel=EMAIL');
  });

  it('omits review_required when false rather than sending false', async () => {
    const spy = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) });
    vi.stubGlobal('fetch', spy);

    await api.conversations({ review_required: false });

    expect(spy.mock.calls[0][0]).toBe('/api/conversations');
  });

  it('posts the review payload as JSON', async () => {
    const spy = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) });
    vi.stubGlobal('fetch', spy);

    await api.review(9, { action: 'EDIT_AND_APPROVE', final_response: 'texto' });

    const [url, init] = spy.mock.calls[0];
    expect(url).toBe('/api/analyses/9/review');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({
      action: 'EDIT_AND_APPROVE',
      final_response: 'texto',
    });
  });
});
