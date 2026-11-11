/**
 * Smoke test for the shell: routing, config loading and the honesty banners.
 *
 * Renders the real App against a stubbed fetch, which catches runtime errors
 * in the layout and pages that a type check cannot.
 */

import { render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';

const CONFIG = {
  ai: {
    demo_mode: true,
    demo_mode_forced: false,
    llm: { provider: 'demo', model: 'demo-rule-engine-v1', temperature: 0, demo_mode: true },
    embeddings: { provider: 'hashing', model: 'local-hashing-384', dimensions: 384 },
    confidence_threshold: 0.75,
    rag_top_k: 5,
    max_retries: 2,
  },
  vector_backend: 'portable-python',
  brokerage_name: 'Correduría Ejemplo',
  data_notice: 'All data in this system is synthetic. No real customers exist.',
};

const DASHBOARD = {
  metrics: {
    open_conversations: 26,
    total_conversations: 42,
    ai_processed_last_24h: 8,
    pending_human_review: 6,
    high_priority_cases: 3,
    avg_confidence: 0.695,
    avg_latency_ms: 96,
    approval_rate: 1,
    edit_rate: 1,
    reviews_recorded: 1,
    customers: 20,
    policies: 39,
    open_tasks: 15,
    knowledge_documents: 10,
    knowledge_chunks: 67,
  },
  distributions: {
    intent: [{ label: 'CLAIM', count: 2 }],
    urgency: [{ label: 'MEDIUM', count: 2 }],
    channel: [{ label: 'WHATSAPP', count: 20 }],
  },
  human_review: { required: 6, reviewed: 1, approved: 0, edited: 1, rejected: 0 },
  recent_conversations: [
    {
      id: 1,
      reference: 'DEMO-01',
      customer_id: 1,
      customer_name: 'Carlos García Ruiz',
      channel: 'WHATSAPP',
      subject: 'Golpe con el coche - documentación',
      status: 'PENDING_REVIEW',
      assigned_team: 'CLAIMS_TEAM',
      created_at: '2026-08-05T09:00:00',
      updated_at: '2026-08-05T09:05:00',
      message_count: 1,
      latest_analysis: {
        id: 1,
        intent: 'CLAIM',
        insurance_type: 'MOTOR',
        urgency: 'MEDIUM',
        confidence: 0.93,
        recommended_action: 'REQUEST_DOCUMENTS',
        assigned_team: 'CLAIMS_TEAM',
        human_review_required: true,
        demo_mode: true,
        reviewed: false,
        reviewer_action: null,
        created_at: '2026-08-05T09:05:00',
      },
    },
  ],
};

function stubApi() {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      const body = url.includes('/config') ? CONFIG : DASHBOARD;
      return Promise.resolve({ ok: true, status: 200, json: async () => body } as Response);
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('App shell', () => {
  it('renders the navigation', async () => {
    stubApi();
    render(<App />);

    expect(await screen.findByText('AI Case Copilot')).toBeInTheDocument();

    // Scope to the sidebar: page bodies also link to /inbox.
    const nav = within(screen.getByRole('navigation'));
    for (const label of [
      'Dashboard',
      'Inbox',
      'Customers',
      'Knowledge Base',
      'Evaluations',
      'Audit Logs',
    ]) {
      expect(nav.getByRole('link', { name: new RegExp(label, 'i') })).toBeInTheDocument();
    }
  });

  it('warns that demo AI mode is active when the backend says so', async () => {
    stubApi();
    render(<App />);

    expect(await screen.findByText('● Demo AI Mode')).toBeInTheDocument();
    expect(screen.getByText(/No LLM API key is configured/i)).toBeInTheDocument();
  });

  it('always states that the data is synthetic', async () => {
    stubApi();
    render(<App />);

    expect(await screen.findByText(/Every customer, policy and conversation/i)).toBeInTheDocument();
  });

  it('renders dashboard metrics from the API', async () => {
    stubApi();
    render(<App />);

    await waitFor(() => expect(screen.getByText('Operations dashboard')).toBeInTheDocument());
    expect(screen.getByText('26')).toBeInTheDocument();
    expect(screen.getByText('96 ms')).toBeInTheDocument();
    expect(screen.getByText('Carlos García Ruiz')).toBeInTheDocument();
  });

  it('shows a live-AI badge when demo mode is off', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        const body = url.includes('/config')
          ? {
              ...CONFIG,
              ai: {
                ...CONFIG.ai,
                demo_mode: false,
                llm: { ...CONFIG.ai.llm, provider: 'anthropic', demo_mode: false },
              },
            }
          : DASHBOARD;
        return Promise.resolve({ ok: true, status: 200, json: async () => body } as Response);
      }),
    );
    render(<App />);

    expect(await screen.findByText(/Live AI — anthropic/)).toBeInTheDocument();
    expect(screen.queryByText('● Demo AI Mode')).not.toBeInTheDocument();
  });

  it('surfaces a backend outage instead of rendering an empty page', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    render(<App />);

    expect(await screen.findByText(/Cannot reach the API/i)).toBeInTheDocument();
  });
});
