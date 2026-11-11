/**
 * Tests for the Copilot panel.
 *
 * These cover behaviour a reviewer would actually check by hand: that the
 * human-review gate is visible, that sources are shown, that editing switches
 * APPROVE to EDIT_AND_APPROVE, and that a safety flag is impossible to miss.
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { CopilotPanel } from './CopilotPanel';
import { claimAnalysis, injectionAnalysis } from '../test/fixtures';

const noop = () => {};

function renderPanel(overrides: Partial<Parameters<typeof CopilotPanel>[0]> = {}) {
  const onReview = vi.fn();
  const onAnalyse = vi.fn();
  render(
    <CopilotPanel
      analysis={claimAnalysis}
      analysing={false}
      analyseError={null}
      reviewError={null}
      reviewPending={false}
      onAnalyse={onAnalyse}
      onReview={onReview}
      {...overrides}
    />,
  );
  return { onReview, onAnalyse };
}

describe('CopilotPanel', () => {
  it('prompts to run the pipeline when there is no analysis', async () => {
    const { onAnalyse } = renderPanel({ analysis: null });

    expect(screen.getByText('Not analysed yet')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /run ai analysis/i }));
    expect(onAnalyse).toHaveBeenCalledWith(false);
  });

  it('shows the classification, confidence and summary', () => {
    renderPanel();

    expect(screen.getByText('Claim')).toBeInTheDocument();
    expect(screen.getByText('Motor')).toBeInTheDocument();
    expect(screen.getByText('MEDIUM')).toBeInTheDocument();
    expect(screen.getByText('93%')).toBeInTheDocument();
    expect(screen.getByText(/damaged bumper/i)).toBeInTheDocument();
  });

  it('renders extracted entities and missing information', () => {
    renderPanel();

    expect(screen.getByText('Vehicle plate')).toBeInTheDocument();
    expect(screen.getByText('1234ABC')).toBeInTheDocument();
    expect(screen.getByText('Injuries')).toBeInTheDocument();
    expect(screen.getByText('No')).toBeInTheDocument();
    expect(screen.getByText('accident photographs')).toBeInTheDocument();
  });

  it('exposes the retrieved RAG sources with their similarity score', () => {
    renderPanel();

    expect(
      screen.getByText('Procedimiento de Siniestros de Automóvil, 3. Documentación obligatoria'),
    ).toBeInTheDocument();
    expect(screen.getByText('0.375')).toBeInTheDocument();
  });

  it('shows the next-best-action and its reason', () => {
    renderPanel();

    expect(screen.getByText('Request documents')).toBeInTheDocument();
    expect(screen.getByText('Claims team')).toBeInTheDocument();
    expect(screen.getByText(/mandatory claim information is missing/i)).toBeInTheDocument();
  });

  it('states why a human must review the draft', () => {
    renderPanel();

    expect(screen.getByText('Human review required')).toBeInTheDocument();
    expect(screen.getByText(/high-risk intent/i)).toBeInTheDocument();
  });

  it('approves the unmodified draft with APPROVE', async () => {
    const { onReview } = renderPanel();

    await userEvent.click(screen.getByRole('button', { name: 'Approve' }));

    expect(onReview).toHaveBeenCalledWith('APPROVE', claimAnalysis.suggested_response, '');
  });

  it('switches to EDIT_AND_APPROVE once the draft is changed', async () => {
    const { onReview } = renderPanel();

    await userEvent.click(screen.getByRole('button', { name: 'Edit' }));
    const textarea = screen.getByLabelText(/edit the suggested response/i);
    await userEvent.clear(textarea);
    await userEvent.type(textarea, 'Texto revisado por el gestor.');
    await userEvent.click(screen.getByRole('button', { name: /save & approve/i }));

    expect(onReview).toHaveBeenCalledWith(
      'EDIT_AND_APPROVE',
      'Texto revisado por el gestor.',
      '',
    );
  });

  it('rejects the draft', async () => {
    const { onReview } = renderPanel();

    await userEvent.click(screen.getByRole('button', { name: 'Reject' }));

    expect(onReview).toHaveBeenCalledWith('REJECT', claimAnalysis.suggested_response, '');
  });

  it('makes clear that nothing is actually sent', () => {
    renderPanel();
    expect(screen.getByText(/delivery is simulated/i)).toBeInTheDocument();
  });

  it('surfaces a prompt-injection safety flag prominently', () => {
    renderPanel({ analysis: injectionAnalysis });

    expect(screen.getByText('Prompt injection suspected')).toBeInTheDocument();
    expect(screen.getByText(/routed to compliance/i)).toBeInTheDocument();
    expect(screen.getByText(/No internal documentation was retrieved/i)).toBeInTheDocument();
  });

  it('shows the review outcome instead of the buttons once reviewed', () => {
    renderPanel({
      analysis: {
        ...claimAnalysis,
        reviews: [
          {
            id: 1,
            ai_analysis_id: claimAnalysis.id,
            reviewer_action: 'APPROVE',
            reviewer_name: 'ana.gestora',
            original_response: claimAnalysis.suggested_response,
            final_response: claimAnalysis.suggested_response,
            reviewer_notes: null,
            simulated_send: true,
            timestamp: '2026-08-05T11:00:00',
          },
        ],
      },
    });

    expect(screen.getByText('ana.gestora', { exact: false })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
  });

  it('reveals model, prompt version and latency in the technical section', async () => {
    renderPanel();

    await userEvent.click(screen.getByText(/technical metadata/i));

    expect(screen.getByText('demo-rule-engine-v1')).toBeInTheDocument();
    expect(screen.getByText('classification_v1')).toBeInTheDocument();
    expect(screen.getByText('96 ms')).toBeInTheDocument();
    expect(screen.getByText('yes (mock output)')).toBeInTheDocument();
  });
});

describe('CopilotPanel error handling', () => {
  it('shows an analysis error', () => {
    render(
      <CopilotPanel
        analysis={null}
        analysing={false}
        analyseError="The AI service is unavailable."
        reviewError={null}
        reviewPending={false}
        onAnalyse={noop}
        onReview={noop}
      />,
    );

    expect(screen.getByText('The AI service is unavailable.')).toBeInTheDocument();
  });

  it('shows a review error', () => {
    renderPanel({ reviewError: 'This analysis has already been reviewed.' });
    expect(
      screen.getByText('This analysis has already been reviewed.'),
    ).toBeInTheDocument();
  });
});

describe('CopilotPanel regressions', () => {
  it('replaces the draft when a re-run produces a new analysis', async () => {
    // The draft lives in local state. Without a remount, "Re-run analysis"
    // left the previous draft in the editor while the rest of the panel
    // showed the new analysis.
    const { rerender } = render(
      <CopilotPanel
        analysis={claimAnalysis}
        analysing={false}
        analyseError={null}
        reviewError={null}
        reviewPending={false}
        onAnalyse={noop}
        onReview={noop}
      />,
    );
    expect(screen.getByText(/Lamentamos lo ocurrido/)).toBeInTheDocument();

    rerender(
      <CopilotPanel
        analysis={{
          ...claimAnalysis,
          id: claimAnalysis.id + 1,
          suggested_response: 'Borrador completamente nuevo tras el re-análisis.',
        }}
        analysing={false}
        analyseError={null}
        reviewError={null}
        reviewPending={false}
        onAnalyse={noop}
        onReview={noop}
      />,
    );

    expect(
      screen.getByText('Borrador completamente nuevo tras el re-análisis.'),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Lamentamos lo ocurrido/)).not.toBeInTheDocument();
  });
});
