/**
 * Single HTTP client for the whole app.
 *
 * There is no mock layer: every screen talks to the real Flask API. The
 * backend's uniform error envelope is unwrapped here once, so components only
 * ever deal with `ApiError`.
 */

import type {
  AnswerResponse,
  AppConfig,
  Analysis,
  AuditList,
  ConversationDetail,
  ConversationList,
  CustomerDetail,
  Customer,
  DashboardData,
  EvaluationList,
  EvaluationRun,
  KnowledgeDocument,
  KnowledgeList,
  ReviewerAction,
  SearchResponse,
  Task,
} from '../types/api';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string = 'error',
    readonly details?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

interface ErrorEnvelope {
  error?: { code?: string; message?: string; details?: unknown };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
      ...init,
    });
  } catch (cause) {
    // fetch only rejects on network failure, which is worth distinguishing
    // from a 500: the backend may simply not be running.
    throw new ApiError(
      'Cannot reach the API. Is the backend running on port 5001?',
      0,
      'network_error',
      cause,
    );
  }

  if (response.status === 204) return undefined as T;

  const payload = (await response.json().catch(() => null)) as (T & ErrorEnvelope) | null;

  if (!response.ok) {
    const envelope = payload as ErrorEnvelope | null;
    throw new ApiError(
      envelope?.error?.message ?? `Request failed with status ${response.status}`,
      response.status,
      envelope?.error?.code ?? 'error',
      envelope?.error?.details,
    );
  }

  return payload as T;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body ?? {}) });

const query = (params: Record<string, string | number | boolean | undefined>) => {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '' && value !== false) {
      search.append(key, String(value));
    }
  }
  const serialised = search.toString();
  return serialised ? `?${serialised}` : '';
};

export interface ConversationFilters {
  search?: string;
  channel?: string;
  status?: string;
  intent?: string;
  urgency?: string;
  insurance_type?: string;
  review_required?: boolean;
}

export const api = {
  config: () => request<AppConfig>('/config'),
  health: () => request<{ status: string; ai_demo_mode: boolean }>('/health'),
  dashboard: () => request<DashboardData>('/dashboard'),

  customers: (search?: string) =>
    request<{ items: Customer[]; count: number }>(`/customers${query({ search })}`),
  customer: (id: number) => request<CustomerDetail>(`/customers/${id}`),

  conversations: (filters: ConversationFilters = {}) =>
    request<ConversationList>(`/conversations${query({ ...filters })}`),
  conversation: (id: number) => request<ConversationDetail>(`/conversations/${id}`),
  analyze: (id: number, force = false) =>
    post<{ analysis: Analysis; conversation: ConversationDetail; tasks: Task[] }>(
      `/conversations/${id}/analyze`,
      { force },
    ),

  review: (
    analysisId: number,
    body: {
      action: ReviewerAction;
      final_response?: string;
      reviewer_notes?: string;
      reviewer_name?: string;
    },
  ) => post<{ review: unknown; analysis: Analysis; note: string }>(
    `/analyses/${analysisId}/review`,
    body,
  ),

  knowledgeDocuments: () => request<KnowledgeList>('/knowledge/documents'),
  knowledgeDocument: (id: number) => request<KnowledgeDocument>(`/knowledge/documents/${id}`),
  ingestKnowledge: (force: boolean) =>
    post<{ report: Record<string, unknown> }>('/knowledge/ingest', { force }),
  searchKnowledge: (queryText: string, topK = 5) =>
    post<SearchResponse>('/knowledge/search', { query: queryText, top_k: topK }),
  answerFromKnowledge: (queryText: string, topK = 5) =>
    post<AnswerResponse>('/knowledge/answer', { query: queryText, top_k: topK }),

  evaluations: () => request<EvaluationList>('/evaluations'),
  evaluationRun: (id: number) => request<EvaluationRun>(`/evaluations/${id}`),
  runEvaluation: (label: string) => post<EvaluationRun>('/evaluations/run', { label }),

  auditLogs: (action?: string) => request<AuditList>(`/audit-logs${query({ action })}`),
};
