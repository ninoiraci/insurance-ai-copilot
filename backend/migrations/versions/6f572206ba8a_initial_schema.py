"""initial schema

Enums are VARCHAR + CHECK (`native_enum=False`) rather than native PostgreSQL
enum types, so extending the taxonomy later is an ordinary migration.

Revision ID: 6f572206ba8a
Revises: 
Create Date: 2026-08-06 04:16:34.122780

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

import app.models.base

# revision identifiers, used by Alembic.
revision = '6f572206ba8a'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # pgvector must exist before any table declares a `vector` column. The
    # `knowledge_chunks.embedding` column compiles to `vector(n)` on
    # PostgreSQL and to JSON elsewhere (see app/models/base.py).
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table('audit_logs',
    sa.Column('action', sa.Enum('AI_ANALYSIS_CREATED', 'AI_ANALYSIS_FAILED', 'AI_OUTPUT_VALIDATION_FAILED', 'BUSINESS_RULE_OVERRIDE', 'PROMPT_INJECTION_SUSPECTED', 'HUMAN_REVIEW_RECORDED', 'RESPONSE_SIMULATED_SEND', 'TASK_CREATED', 'KNOWLEDGE_INGESTED', 'KNOWLEDGE_SEARCHED', 'EVALUATION_RUN', name='auditaction', native_enum=False, length=40), nullable=False),
    sa.Column('entity_type', sa.String(length=60), nullable=False),
    sa.Column('entity_id', sa.Integer(), nullable=True),
    sa.Column('actor', sa.String(length=80), nullable=False),
    sa.Column('request_id', sa.String(length=40), nullable=True),
    sa.Column('metadata', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_logs_action'), ['action'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_entity_id'), ['entity_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_entity_type'), ['entity_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_request_id'), ['request_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_timestamp'), ['timestamp'], unique=False)

    op.create_table('customers',
    sa.Column('full_name', sa.String(length=160), nullable=False),
    sa.Column('email', sa.String(length=200), nullable=True),
    sa.Column('phone', sa.String(length=40), nullable=True),
    sa.Column('preferred_language', sa.String(length=8), nullable=False),
    sa.Column('city', sa.String(length=80), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_customers_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_customers_full_name'), ['full_name'], unique=False)

    op.create_table('evaluation_cases',
    sa.Column('case_key', sa.String(length=40), nullable=False),
    sa.Column('input_text', sa.Text(), nullable=False),
    sa.Column('channel', sa.String(length=20), nullable=False),
    sa.Column('difficulty', sa.String(length=20), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('expected_intent', sa.Enum('CLAIM', 'RENEWAL', 'NEW_QUOTE', 'PAYMENT', 'DOCUMENT_REQUEST', 'POLICY_INFORMATION', 'POLICY_CHANGE', 'CANCELLATION', 'COMPLAINT', 'CROSS_SELL', 'GENERAL_SUPPORT', 'UNKNOWN', name='intent', native_enum=False, length=40), nullable=False),
    sa.Column('expected_urgency', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='urgency', native_enum=False, length=40), nullable=False),
    sa.Column('expected_insurance_type', sa.Enum('MOTOR', 'HOME', 'LIFE', 'HEALTH', 'TRAVEL', 'BUSINESS', 'OTHER', 'UNKNOWN', name='insurancetype', native_enum=False, length=40), nullable=False),
    sa.Column('expected_action', sa.Enum('REQUEST_DOCUMENTS', 'CREATE_CLAIM_CASE', 'ASSIGN_TO_CLAIMS', 'ASSIGN_TO_SALES', 'ASSIGN_TO_ADMIN', 'SCHEDULE_FOLLOW_UP', 'SEND_POLICY_INFORMATION', 'PREPARE_QUOTE', 'ESCALATE_TO_HUMAN', 'RENEWAL_CONTACT', 'CANCELLATION_WORKFLOW', 'REQUEST_CLARIFICATION', 'NO_ACTION', name='recommendedaction', native_enum=False, length=40), nullable=False),
    sa.Column('expected_entities', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('expects_human_review', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('case_key')
    )
    with op.batch_alter_table('evaluation_cases', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_evaluation_cases_created_at'), ['created_at'], unique=False)

    op.create_table('evaluation_runs',
    sa.Column('label', sa.String(length=120), nullable=False),
    sa.Column('model_name', sa.String(length=80), nullable=False),
    sa.Column('prompt_version', sa.String(length=40), nullable=False),
    sa.Column('demo_mode', sa.Boolean(), nullable=False),
    sa.Column('case_count', sa.Integer(), nullable=False),
    sa.Column('metrics', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('evaluation_runs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_evaluation_runs_created_at'), ['created_at'], unique=False)

    op.create_table('knowledge_documents',
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('category', sa.String(length=80), nullable=False),
    sa.Column('source_filename', sa.String(length=200), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('char_count', sa.Integer(), nullable=False),
    sa.Column('raw_content', sa.Text(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source_filename')
    )
    with op.batch_alter_table('knowledge_documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_knowledge_documents_category'), ['category'], unique=False)
        batch_op.create_index(batch_op.f('ix_knowledge_documents_created_at'), ['created_at'], unique=False)

    op.create_table('conversations',
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('channel', sa.Enum('WHATSAPP', 'EMAIL', 'PHONE_CALL', name='channel', native_enum=False, length=40), nullable=False),
    sa.Column('subject', sa.String(length=200), nullable=False),
    sa.Column('status', sa.Enum('NEW', 'AI_PROCESSED', 'PENDING_REVIEW', 'AWAITING_CUSTOMER', 'RESOLVED', 'ESCALATED', name='conversationstatus', native_enum=False, length=40), nullable=False),
    sa.Column('assigned_team', sa.Enum('CLAIMS_TEAM', 'SALES_TEAM', 'ADMIN_TEAM', 'CUSTOMER_SUCCESS', 'COMPLIANCE_TEAM', 'UNASSIGNED', name='team', native_enum=False, length=40), nullable=False),
    sa.Column('reference', sa.String(length=40), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('reference')
    )
    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_conversations_assigned_team'), ['assigned_team'], unique=False)
        batch_op.create_index(batch_op.f('ix_conversations_channel'), ['channel'], unique=False)
        batch_op.create_index(batch_op.f('ix_conversations_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_conversations_customer_id'), ['customer_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_conversations_status'), ['status'], unique=False)

    op.create_table('evaluation_results',
    sa.Column('run_id', sa.Integer(), nullable=False),
    sa.Column('case_key', sa.String(length=40), nullable=False),
    sa.Column('predicted', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('expected', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('correctness', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('latency_ms', sa.Integer(), nullable=False),
    sa.Column('schema_valid', sa.Boolean(), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['evaluation_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('evaluation_results', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_evaluation_results_run_id'), ['run_id'], unique=False)

    op.create_table('knowledge_chunks',
    sa.Column('document_id', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('section', sa.String(length=200), nullable=True),
    sa.Column('embedding', app.models.base.EmbeddingColumn(), nullable=True),
    sa.Column('embedding_model', sa.String(length=80), nullable=True),
    sa.Column('metadata', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['knowledge_documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('document_id', 'chunk_index', name='uq_chunk_document_index')
    )
    with op.batch_alter_table('knowledge_chunks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_knowledge_chunks_document_id'), ['document_id'], unique=False)

    op.create_table('policies',
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('policy_number', sa.String(length=40), nullable=False),
    sa.Column('policy_type', sa.Enum('MOTOR', 'HOME', 'LIFE', 'HEALTH', 'TRAVEL', 'BUSINESS', 'OTHER', 'UNKNOWN', name='insurancetype', native_enum=False, length=40), nullable=False),
    sa.Column('provider', sa.String(length=80), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('expiration_date', sa.Date(), nullable=False),
    sa.Column('status', sa.Enum('ACTIVE', 'LAPSED', 'CANCELLED', 'PENDING_RENEWAL', name='policystatus', native_enum=False, length=40), nullable=False),
    sa.Column('annual_premium', sa.Float(), nullable=True),
    sa.Column('vehicle_plate', sa.String(length=16), nullable=True),
    sa.Column('property_address', sa.String(length=200), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('policy_number')
    )
    with op.batch_alter_table('policies', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_policies_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_policies_customer_id'), ['customer_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_policies_expiration_date'), ['expiration_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_policies_policy_type'), ['policy_type'], unique=False)

    op.create_table('messages',
    sa.Column('conversation_id', sa.Integer(), nullable=False),
    sa.Column('sender_type', sa.Enum('CUSTOMER', 'AGENT', 'SYSTEM', name='sendertype', native_enum=False, length=40), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_messages_conversation_id'), ['conversation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_messages_timestamp'), ['timestamp'], unique=False)

    op.create_table('ai_analyses',
    sa.Column('conversation_id', sa.Integer(), nullable=False),
    sa.Column('message_id', sa.Integer(), nullable=True),
    sa.Column('intent', sa.Enum('CLAIM', 'RENEWAL', 'NEW_QUOTE', 'PAYMENT', 'DOCUMENT_REQUEST', 'POLICY_INFORMATION', 'POLICY_CHANGE', 'CANCELLATION', 'COMPLAINT', 'CROSS_SELL', 'GENERAL_SUPPORT', 'UNKNOWN', name='intent', native_enum=False, length=40), nullable=False),
    sa.Column('insurance_type', sa.Enum('MOTOR', 'HOME', 'LIFE', 'HEALTH', 'TRAVEL', 'BUSINESS', 'OTHER', 'UNKNOWN', name='insurancetype', native_enum=False, length=40), nullable=False),
    sa.Column('urgency', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='urgency', native_enum=False, length=40), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('extracted_entities', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('missing_information', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('recommended_action', sa.Enum('REQUEST_DOCUMENTS', 'CREATE_CLAIM_CASE', 'ASSIGN_TO_CLAIMS', 'ASSIGN_TO_SALES', 'ASSIGN_TO_ADMIN', 'SCHEDULE_FOLLOW_UP', 'SEND_POLICY_INFORMATION', 'PREPARE_QUOTE', 'ESCALATE_TO_HUMAN', 'RENEWAL_CONTACT', 'CANCELLATION_WORKFLOW', 'REQUEST_CLARIFICATION', 'NO_ACTION', name='recommendedaction', native_enum=False, length=40), nullable=False),
    sa.Column('assigned_team', sa.Enum('CLAIMS_TEAM', 'SALES_TEAM', 'ADMIN_TEAM', 'CUSTOMER_SUCCESS', 'COMPLIANCE_TEAM', 'UNASSIGNED', name='team', native_enum=False, length=40), nullable=False),
    sa.Column('action_reason', sa.Text(), nullable=True),
    sa.Column('follow_up_hours', sa.Integer(), nullable=True),
    sa.Column('suggested_response', sa.Text(), nullable=False),
    sa.Column('human_review_required', sa.Boolean(), nullable=False),
    sa.Column('review_reasons', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('retrieved_sources', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('grounded', sa.Boolean(), nullable=False),
    sa.Column('model_name', sa.String(length=80), nullable=False),
    sa.Column('prompt_version', sa.String(length=40), nullable=False),
    sa.Column('processing_latency_ms', sa.Integer(), nullable=False),
    sa.Column('demo_mode', sa.Boolean(), nullable=False),
    sa.Column('validation_attempts', sa.Integer(), nullable=False),
    sa.Column('rule_overrides', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('safety_flags', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('token_usage', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('ai_analyses', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ai_analyses_conversation_id'), ['conversation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_ai_analyses_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_ai_analyses_human_review_required'), ['human_review_required'], unique=False)
        batch_op.create_index(batch_op.f('ix_ai_analyses_insurance_type'), ['insurance_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_ai_analyses_intent'), ['intent'], unique=False)
        batch_op.create_index(batch_op.f('ix_ai_analyses_message_id'), ['message_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_ai_analyses_recommended_action'), ['recommended_action'], unique=False)
        batch_op.create_index(batch_op.f('ix_ai_analyses_urgency'), ['urgency'], unique=False)

    op.create_table('human_reviews',
    sa.Column('ai_analysis_id', sa.Integer(), nullable=False),
    sa.Column('reviewer_action', sa.Enum('APPROVE', 'EDIT_AND_APPROVE', 'REJECT', name='revieweraction', native_enum=False, length=40), nullable=False),
    sa.Column('reviewer_name', sa.String(length=120), nullable=False),
    sa.Column('original_response', sa.Text(), nullable=False),
    sa.Column('final_response', sa.Text(), nullable=True),
    sa.Column('reviewer_notes', sa.Text(), nullable=True),
    sa.Column('simulated_send', sa.Boolean(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['ai_analysis_id'], ['ai_analyses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('human_reviews', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_human_reviews_ai_analysis_id'), ['ai_analysis_id'], unique=False)

    op.create_table('tasks',
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('conversation_id', sa.Integer(), nullable=True),
    sa.Column('ai_analysis_id', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('assigned_team', sa.Enum('CLAIMS_TEAM', 'SALES_TEAM', 'ADMIN_TEAM', 'CUSTOMER_SUCCESS', 'COMPLIANCE_TEAM', 'UNASSIGNED', name='team', native_enum=False, length=40), nullable=False),
    sa.Column('priority', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='taskpriority', native_enum=False, length=40), nullable=False),
    sa.Column('status', sa.Enum('OPEN', 'IN_PROGRESS', 'DONE', 'CANCELLED', name='taskstatus', native_enum=False, length=40), nullable=False),
    sa.Column('due_at', sa.DateTime(), nullable=True),
    sa.Column('source', sa.String(length=40), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['ai_analysis_id'], ['ai_analyses.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tasks_ai_analysis_id'), ['ai_analysis_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tasks_assigned_team'), ['assigned_team'], unique=False)
        batch_op.create_index(batch_op.f('ix_tasks_conversation_id'), ['conversation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tasks_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_tasks_customer_id'), ['customer_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tasks_status'), ['status'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tasks_status'))
        batch_op.drop_index(batch_op.f('ix_tasks_customer_id'))
        batch_op.drop_index(batch_op.f('ix_tasks_created_at'))
        batch_op.drop_index(batch_op.f('ix_tasks_conversation_id'))
        batch_op.drop_index(batch_op.f('ix_tasks_assigned_team'))
        batch_op.drop_index(batch_op.f('ix_tasks_ai_analysis_id'))

    op.drop_table('tasks')
    with op.batch_alter_table('human_reviews', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_human_reviews_ai_analysis_id'))

    op.drop_table('human_reviews')
    with op.batch_alter_table('ai_analyses', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ai_analyses_urgency'))
        batch_op.drop_index(batch_op.f('ix_ai_analyses_recommended_action'))
        batch_op.drop_index(batch_op.f('ix_ai_analyses_message_id'))
        batch_op.drop_index(batch_op.f('ix_ai_analyses_intent'))
        batch_op.drop_index(batch_op.f('ix_ai_analyses_insurance_type'))
        batch_op.drop_index(batch_op.f('ix_ai_analyses_human_review_required'))
        batch_op.drop_index(batch_op.f('ix_ai_analyses_created_at'))
        batch_op.drop_index(batch_op.f('ix_ai_analyses_conversation_id'))

    op.drop_table('ai_analyses')
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_messages_timestamp'))
        batch_op.drop_index(batch_op.f('ix_messages_conversation_id'))

    op.drop_table('messages')
    with op.batch_alter_table('policies', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_policies_policy_type'))
        batch_op.drop_index(batch_op.f('ix_policies_expiration_date'))
        batch_op.drop_index(batch_op.f('ix_policies_customer_id'))
        batch_op.drop_index(batch_op.f('ix_policies_created_at'))

    op.drop_table('policies')
    with op.batch_alter_table('knowledge_chunks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_knowledge_chunks_document_id'))

    op.drop_table('knowledge_chunks')
    with op.batch_alter_table('evaluation_results', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_evaluation_results_run_id'))

    op.drop_table('evaluation_results')
    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_conversations_status'))
        batch_op.drop_index(batch_op.f('ix_conversations_customer_id'))
        batch_op.drop_index(batch_op.f('ix_conversations_created_at'))
        batch_op.drop_index(batch_op.f('ix_conversations_channel'))
        batch_op.drop_index(batch_op.f('ix_conversations_assigned_team'))

    op.drop_table('conversations')
    with op.batch_alter_table('knowledge_documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_knowledge_documents_created_at'))
        batch_op.drop_index(batch_op.f('ix_knowledge_documents_category'))

    op.drop_table('knowledge_documents')
    with op.batch_alter_table('evaluation_runs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_evaluation_runs_created_at'))

    op.drop_table('evaluation_runs')
    with op.batch_alter_table('evaluation_cases', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_evaluation_cases_created_at'))

    op.drop_table('evaluation_cases')
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_customers_full_name'))
        batch_op.drop_index(batch_op.f('ix_customers_created_at'))

    op.drop_table('customers')
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_logs_timestamp'))
        batch_op.drop_index(batch_op.f('ix_audit_logs_request_id'))
        batch_op.drop_index(batch_op.f('ix_audit_logs_entity_type'))
        batch_op.drop_index(batch_op.f('ix_audit_logs_entity_id'))
        batch_op.drop_index(batch_op.f('ix_audit_logs_action'))

    op.drop_table('audit_logs')
    # ### end Alembic commands ###
