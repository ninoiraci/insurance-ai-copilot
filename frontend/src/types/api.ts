/**
 * Types mirroring the backend's JSON contracts.
 *
 * These are hand-written rather than generated: the API surface is small, and
 * a reviewer can read the whole contract in one file. The enums are kept in
 * sync with backend/app/models/enums.py - a mismatch surfaces immediately
 * because the UI renders labels from these unions.
 */

export type Intent =
  | 'CLAIM'
  | 'RENEWAL'
  | 'NEW_QUOTE'
  | 'PAYMENT'
  | 'DOCUMENT_REQUEST'
  | 'POLICY_INFORMATION'
  | 'POLICY_CHANGE'
  | 'CANCELLATION'
  | 'COMPLAINT'
  | 'CROSS_SELL'
  | 'GENERAL_SUPPORT'
  | 'UNKNOWN';

export type InsuranceType =
  | 'MOTOR'
  | 'HOME'
  | 'LIFE'
  | 'HEALTH'
  | 'TRAVEL'
  | 'BUSINESS'
  | 'OTHER'
  | 'UNKNOWN';

export type Urgency = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type Channel = 'WHATSAPP' | 'EMAIL' | 'PHONE_CALL';

export type ConversationStatus =
  | 'NEW'
  | 'AI_PROCESSED'
  | 'PENDING_REVIEW'
  | 'AWAITING_CUSTOMER'
  | 'RESOLVED'
  | 'ESCALATED';

export type ReviewerAction = 'APPROVE' | 'EDIT_AND_APPROVE' | 'REJECT';

export interface Policy {
  id: number;
  customer_id: number;
  policy_number: string;
  policy_type: InsuranceType;
  provider: string;
  start_date: string;
  expiration_date: string;
  status: string;
  annual_premium: number | null;
  vehicle_plate: string | null;
  property_address: string | null;
  days_to_expiration: number;
}

export interface Task {
  id: number;
  customer_id: number;
  customer_name: string | null;
  conversation_id: number | null;
  title: string;
  description: string | null;
  assigned_team: string;
  priority: Urgency;
  status: string;
  due_at: string | null;
  source: string;
  created_at: string;
}

export interface Customer {
  id: number;
  full_name: string;
  email: string | null;
  phone: string | null;
  preferred_language: string;
  city: string | null;
  notes: string | null;
  created_at: string;
  policy_count?: number;
  conversation_count?: number;
  open_task_count?: number;
  policies?: Policy[];
  tasks?: Task[];
  conversations?: Conversation[];
}

export interface Message {
  id: number;
  conversation_id: number;
  sender_type: 'CUSTOMER' | 'AGENT' | 'SYSTEM';
  content: string;
  timestamp: string;
}

export interface RetrievedSource {
  chunk_id: number;
  document_id: number;
  document_title: string;
  section: string;
  content: string;
  similarity: number;
  citation: string;
  category: string;
}

export interface RuleOverride {
  rule: string;
  from: Urgency;
  to: Urgency;
  reason: string;
}

export interface HumanReview {
  id: number;
  ai_analysis_id: number;
  reviewer_action: ReviewerAction;
  reviewer_name: string;
  original_response: string;
  final_response: string | null;
  reviewer_notes: string | null;
  simulated_send: boolean;
  timestamp: string;
}

export interface AnalysisSummary {
  id: number;
  intent: Intent;
  insurance_type: InsuranceType;
  urgency: Urgency;
  confidence: number;
  recommended_action: string;
  assigned_team: string;
  human_review_required: boolean;
  demo_mode: boolean;
  reviewed: boolean;
  reviewer_action: ReviewerAction | null;
  created_at: string;
}

export interface Analysis extends AnalysisSummary {
  conversation_id: number;
  message_id: number | null;
  summary: string;
  extracted_entities: Record<string, unknown>;
  missing_information: string[];
  action_reason: string | null;
  follow_up_hours: number | null;
  suggested_response: string;
  review_reasons: string[];
  retrieved_sources: RetrievedSource[];
  grounded: boolean;
  rule_overrides: RuleOverride[];
  safety_flags: string[];
  reviews: HumanReview[];
  metadata: {
    model_name: string;
    prompt_version: string;
    processing_latency_ms: number;
    demo_mode: boolean;
    validation_attempts: number;
    retrieved_chunk_count: number;
    token_usage: Record<string, number> | null;
    created_at: string;
  };
}

export interface Conversation {
  id: number;
  reference: string | null;
  customer_id: number;
  customer_name: string | null;
  channel: Channel;
  subject: string;
  status: ConversationStatus;
  assigned_team: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  latest_analysis: AnalysisSummary | null;
  preview?: string;
  messages?: Message[];
}

export interface CustomerContext {
  customer_id: number;
  full_name: string;
  preferred_language: string;
  policies: Array<{
    policy_number: string;
    policy_type: InsuranceType;
    provider: string;
    status: string;
    expiration_date: string;
    days_to_expiration: number;
    vehicle_plate: string | null;
  }>;
  recent_interactions: Array<{
    date: string;
    channel: Channel;
    subject: string;
    status: string;
  }>;
  open_tasks: Array<{ title: string; priority: Urgency; team: string }>;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
  customer: Customer;
  ai_context: CustomerContext;
  analyses: Analysis[];
  tasks: Task[];
}

export interface ConversationList {
  items: Conversation[];
  count: number;
  filters: {
    channels: Channel[];
    statuses: ConversationStatus[];
    intents: Intent[];
    urgencies: Urgency[];
    insurance_types: InsuranceType[];
  };
}

export interface CustomerDetail extends Customer {
  policies: Policy[];
  tasks: Task[];
  conversations: Conversation[];
  ai_context: CustomerContext;
  ai_case_history: AnalysisSummary[];
}

export interface DashboardData {
  metrics: {
    open_conversations: number;
    total_conversations: number;
    ai_processed_last_24h: number;
    pending_human_review: number;
    high_priority_cases: number;
    avg_confidence: number;
    avg_latency_ms: number;
    approval_rate: number | null;
    edit_rate: number | null;
    reviews_recorded: number;
    customers: number;
    policies: number;
    open_tasks: number;
    knowledge_documents: number;
    knowledge_chunks: number;
  };
  distributions: {
    intent: Array<{ label: string; count: number }>;
    urgency: Array<{ label: string; count: number }>;
    channel: Array<{ label: string; count: number }>;
  };
  human_review: {
    required: number;
    reviewed: number;
    approved: number;
    edited: number;
    rejected: number;
  };
  recent_conversations: Conversation[];
}

export interface KnowledgeDocument {
  id: number;
  title: string;
  category: string;
  source_filename: string;
  chunk_count: number;
  char_count: number;
  content_hash: string;
  created_at: string;
  raw_content?: string;
  chunks?: Array<{
    id: number;
    chunk_index: number;
    section: string | null;
    content: string;
    citation: string | null;
  }>;
}

export interface KnowledgeList {
  items: KnowledgeDocument[];
  count: number;
  embedding: { provider: string; model: string; dimensions: number };
  vector_backend: string;
  source_directory: string;
}

export interface SearchResponse {
  query: string;
  results: RetrievedSource[];
  count: number;
  vector_backend: string;
  embedding: { provider: string; model: string; dimensions: number };
  min_similarity: number;
}

export interface AnswerResponse extends Omit<SearchResponse, 'min_similarity'> {
  answer: string;
  grounded: boolean;
  insufficient_information: boolean;
  used_sources: string[];
  metadata: {
    model: string;
    prompt_version: string;
    latency_ms: number;
    attempts: number;
    demo_mode: boolean;
  };
}

export interface EntityMetrics {
  true_positive: number;
  false_positive: number;
  false_negative: number;
  precision: number;
  recall: number;
  f1: number;
}

export interface EvaluationMetrics {
  cases: number;
  intent_accuracy: number;
  urgency_accuracy: number;
  insurance_type_accuracy: number;
  action_accuracy: number;
  schema_validation_rate: number;
  entity_extraction: EntityMetrics;
  human_review_recall_on_risky: number;
  human_review_false_alarm_rate: number;
  risky_cases: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  total_input_tokens: number;
  total_output_tokens: number;
  intent_confusion: Record<string, Record<string, number>>;
}

export interface EvaluationResult {
  id: number;
  run_id: number;
  case_key: string;
  predicted: Record<string, unknown>;
  expected: Record<string, unknown>;
  correctness: Record<string, boolean | number>;
  latency_ms: number;
  schema_valid: boolean;
  error: string | null;
}

export interface EvaluationRun {
  id: number;
  label: string;
  model_name: string;
  prompt_version: string;
  demo_mode: boolean;
  case_count: number;
  metrics: EvaluationMetrics;
  duration_ms: number;
  created_at: string;
  results?: EvaluationResult[];
}

export interface EvaluationList {
  items: EvaluationRun[];
  count: number;
  dataset_size: number;
  latest: EvaluationRun | null;
}

export interface EvaluationCase {
  id: number;
  case_key: string;
  input_text: string;
  channel: string;
  difficulty: string;
  notes: string | null;
  expected_intent: Intent;
  expected_urgency: Urgency;
  expected_insurance_type: InsuranceType;
  expected_action: string;
  expected_entities: Record<string, unknown>;
  expects_human_review: boolean;
}

export interface AuditEntry {
  id: number;
  action: string;
  entity_type: string;
  entity_id: number | null;
  actor: string;
  request_id: string | null;
  metadata: Record<string, unknown>;
  timestamp: string;
}

export interface AuditList {
  items: AuditEntry[];
  count: number;
  actions: string[];
}

export interface AppConfig {
  ai: {
    demo_mode: boolean;
    demo_mode_forced: boolean;
    llm: { provider: string; model: string; temperature: number; demo_mode: boolean };
    embeddings: { provider: string; model: string; dimensions: number };
    confidence_threshold: number;
    rag_top_k: number;
    max_retries: number;
  };
  vector_backend: string;
  brokerage_name: string;
  data_notice: string;
}
