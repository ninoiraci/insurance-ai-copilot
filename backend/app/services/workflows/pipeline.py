"""The AI case pipeline: one orchestrator, many small services.

    normalize -> customer context -> LLM classification -> schema validation
      -> business rules -> RAG retrieval -> next-best-action
      -> grounded response -> review gate -> persistence + audit

Each arrow is a separate, individually testable module. This file only wires
them together and owns the failure policy, so the flow can be read top to
bottom without opening anything else.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import timedelta

from ...config import AISettings
from ...extensions import db
from ...models import (
    AIAnalysis,
    AuditAction,
    Conversation,
    ConversationStatus,
    Intent,
    Message,
    RecommendedAction,
    Task,
    TaskPriority,
    TaskStatus,
    Urgency,
    utcnow,
)
from ...prompts import CLASSIFICATION_PROMPT, get_prompt
from ...schemas.ai_output import (
    AnalysisFailure,
    GeneratedResponse,
    MessageAnalysis,
)
from ...utils.text import (
    content_fingerprint,
    detect_injection,
    normalize_message,
    redact,
)
from ..ai.factory import AIStack
from ..audit import record_audit
from ..rag.retriever import KnowledgeRetriever
from ..rag.vector_store import RetrievedChunk
from .action_engine import ROUTING_CONFIDENCE_FLOOR, ActionDecision, decide_action
from .business_rules import BusinessRuleResult, apply_business_rules
from .context import CustomerContext, build_customer_context
from .response_generation import generate_response
from .review_policy import ReviewDecision, decide_review

logger = logging.getLogger(__name__)

MAX_MESSAGE_CHARS = 8000


@dataclass
class PipelineResult:
    analysis: MessageAnalysis
    rules: BusinessRuleResult
    action: ActionDecision
    review: ReviewDecision
    response: GeneratedResponse
    retrieved: list[RetrievedChunk] = field(default_factory=list)
    model_name: str = "unknown"
    prompt_version: str = CLASSIFICATION_PROMPT
    latency_ms: int = 0
    attempts: int = 1
    demo_mode: bool = False
    fallback_used: bool = False
    token_usage: dict | None = None


class AnalysisPipeline:
    def __init__(
        self, ai: AIStack, settings: AISettings, *, log_message_bodies: bool = False
    ) -> None:
        self.ai = ai
        self.settings = settings
        # Customer message content stays out of the logs unless an operator
        # explicitly opts in (LOG_MESSAGE_BODIES).
        self.log_message_bodies = log_message_bodies
        self.retriever = KnowledgeRetriever(
            ai.embeddings,
            top_k=settings.rag_top_k,
            min_similarity=settings.rag_min_similarity,
        )

    # -- stage 1..9: pure analysis, no database writes -----------------------

    def run(
        self,
        *,
        raw_message: str,
        context: CustomerContext | None,
        channel: str = "WHATSAPP",
    ) -> PipelineResult:
        started = time.perf_counter()

        message = normalize_message(raw_message)[:MAX_MESSAGE_CHARS]
        if not message:
            raise ValueError("cannot analyse an empty message")

        injection_hits = detect_injection(message)
        if injection_hits:
            # An excerpt is genuinely useful when triaging a flagged message,
            # but it is still customer content, so it is opt-in and redacted.
            if self.log_message_bodies:
                logger.warning(
                    "prompt_injection_suspected patterns=%s excerpt=%s",
                    len(injection_hits),
                    redact(message, max_length=80),
                )
            else:
                logger.warning(
                    "prompt_injection_suspected patterns=%s fingerprint=%s",
                    len(injection_hits),
                    content_fingerprint(message)[:12],
                )

        analysis, attempts, fallback_used, token_usage = self._classify(
            message, context, channel
        )

        # From here on `rules.urgency` is the authoritative value. `analysis`
        # is left untouched so it stays a faithful record of what the model
        # actually said - the two are compared in `rule_overrides`.
        rules = apply_business_rules(analysis, context, raw_message=message)

        retrieved = self._retrieve(message, analysis, rules)
        action = decide_action(analysis, rules, context)

        response, response_attempts = generate_response(
            self.ai.client,
            analysis=analysis,
            urgency=rules.urgency,
            action=action,
            context=context,
            retrieved=retrieved,
            message=message,
        )

        review = decide_review(
            analysis,
            rules,
            action,
            response,
            confidence_threshold=self.settings.confidence_threshold,
            demo_mode=self.ai.demo_mode,
        )

        return PipelineResult(
            analysis=analysis,
            rules=rules,
            action=action,
            review=review,
            response=response,
            retrieved=retrieved,
            model_name=self.ai.client.model_name,
            prompt_version=CLASSIFICATION_PROMPT,
            latency_ms=int((time.perf_counter() - started) * 1000),
            attempts=attempts + response_attempts,
            demo_mode=self.ai.demo_mode,
            fallback_used=fallback_used,
            token_usage=token_usage,
        )

    def _classify(
        self, message: str, context: CustomerContext | None, channel: str
    ) -> tuple[MessageAnalysis, int, bool, dict | None]:
        """Return (analysis, attempts, fallback_used, token_usage)."""
        prompt = get_prompt(CLASSIFICATION_PROMPT)
        system, user = prompt.render(
            allowed_values=MessageAnalysis.json_schema_prompt_fragment(),
            customer_context=(
                context.to_prompt_block() if context else "No customer record available."
            ),
            channel=channel,
            message=message,
        )

        try:
            analysis, raw, attempts = self.ai.client.generate(
                schema=MessageAnalysis, system=system, user=user, label="classification"
            )
            return analysis, attempts, False, raw.token_usage
        except AnalysisFailure as exc:
            # The model failed us. Fail *safe*, not silent: produce a minimal,
            # honest analysis that forces the case in front of a human.
            logger.error("classification_failed attempts=%s error=%s", exc.attempts, exc)
            record_audit(
                AuditAction.AI_OUTPUT_VALIDATION_FAILED,
                entity_type="AIAnalysis",
                metadata={"attempts": exc.attempts, "error": str(exc)[:400]},
            )
            return self._fallback_analysis(), exc.attempts, True, None

    @staticmethod
    def _fallback_analysis() -> MessageAnalysis:
        return MessageAnalysis(
            intent=Intent.UNKNOWN,
            insurance_type="UNKNOWN",
            urgency=Urgency.MEDIUM,
            confidence=0.0,
            summary=(
                "The AI analysis could not be completed reliably. This case has not been "
                "classified and requires manual triage."
            ),
            missing_information=["complete manual triage"],
            recommended_action=RecommendedAction.ESCALATE_TO_HUMAN,
            human_review_required=True,
            reasoning="Structured output validation failed after all retries.",
        )

    def _retrieve(
        self, message: str, analysis: MessageAnalysis, rules: BusinessRuleResult
    ) -> list[RetrievedChunk]:
        # Do not feed suspected injection text into a retrieval query - it is
        # not a description of an insurance need, and grounding it is pointless.
        if "PROMPT_INJECTION_SUSPECTED" in rules.safety_flags:
            return []

        # If we do not know what the customer wants, we cannot know which
        # procedure is relevant. Retrieving anyway produces confident-looking
        # citations for an answer nobody should trust, so we retrieve nothing
        # and let the response generator say so honestly.
        if analysis.confidence < ROUTING_CONFIDENCE_FLOOR or analysis.intent in {
            Intent.UNKNOWN,
            Intent.GENERAL_SUPPORT,
        }:
            logger.info(
                "rag_skipped reason=low_confidence_or_unclear_intent intent=%s confidence=%.2f",
                analysis.intent.value,
                analysis.confidence,
            )
            return []
        try:
            return self.retriever.retrieve_for_case(
                message, analysis.intent, analysis.insurance_type
            )
        except Exception:
            # Retrieval is an enhancement; losing it must not lose the analysis.
            logger.exception("rag_retrieval_failed")
            return []

    # -- stage 10: persistence + audit ---------------------------------------

    def analyze_conversation(
        self, conversation: Conversation, *, message: Message | None = None
    ) -> AIAnalysis:
        target = message or conversation.latest_customer_message
        if target is None:
            raise ValueError("conversation has no customer message to analyse")

        context = build_customer_context(
            conversation.customer, exclude_conversation_id=conversation.id
        )
        result = self.run(
            raw_message=target.content,
            context=context,
            channel=conversation.channel.value,
        )

        # One transaction: the analysis, the routing change, the work item and
        # the audit trail either all land or none of them do.
        record = self._save_analysis(conversation, target, result)
        self._route_conversation(conversation, result)
        self._create_task(conversation, record, result)
        self._audit(conversation, record, result)

        db.session.commit()
        return record

    @staticmethod
    def _save_analysis(
        conversation: Conversation, target: Message, result: PipelineResult
    ) -> AIAnalysis:
        record = AIAnalysis(
            conversation_id=conversation.id,
            message_id=target.id,
            **result.analysis.to_storage_dict(),
            # Urgency comes from the rule engine, not the model.
            urgency=result.rules.urgency,
            recommended_action=result.action.recommended_action,
            assigned_team=result.action.assign_to,
            action_reason=result.action.reason,
            follow_up_hours=result.action.follow_up_hours,
            suggested_response=result.response.response_text,
            human_review_required=result.review.required,
            review_reasons=result.review.reasons,
            retrieved_sources=[chunk.to_dict() for chunk in result.retrieved],
            grounded=result.response.grounded,
            model_name=result.model_name,
            prompt_version=result.prompt_version,
            processing_latency_ms=result.latency_ms,
            demo_mode=result.demo_mode,
            validation_attempts=result.attempts,
            rule_overrides=result.rules.override_dicts(),
            safety_flags=result.rules.safety_flags,
            token_usage=result.token_usage,
        )
        db.session.add(record)
        db.session.flush()  # assigns record.id, needed by the task and audit rows
        return record

    @staticmethod
    def _route_conversation(conversation: Conversation, result: PipelineResult) -> None:
        conversation.assigned_team = result.action.assign_to
        conversation.status = (
            ConversationStatus.PENDING_REVIEW
            if result.review.required
            else ConversationStatus.AI_PROCESSED
        )
        conversation.updated_at = utcnow()

    @staticmethod
    def _audit(
        conversation: Conversation, record: AIAnalysis, result: PipelineResult
    ) -> None:
        if result.rules.safety_flags:
            record_audit(
                AuditAction.PROMPT_INJECTION_SUSPECTED,
                entity_type="Conversation",
                entity_id=conversation.id,
                metadata={
                    "flags": result.rules.safety_flags,
                    "analysis_id": record.id,
                },
            )

        for override in result.rules.overrides:
            record_audit(
                AuditAction.BUSINESS_RULE_OVERRIDE,
                entity_type="AIAnalysis",
                entity_id=record.id,
                metadata=override.to_dict(),
            )

        record_audit(
            AuditAction.AI_ANALYSIS_FAILED
            if result.fallback_used
            else AuditAction.AI_ANALYSIS_CREATED,
            entity_type="AIAnalysis",
            entity_id=record.id,
            metadata={
                "conversation_id": conversation.id,
                "intent": record.intent.value,
                "urgency": record.urgency.value,
                "confidence": round(record.confidence, 3),
                "action": record.recommended_action.value,
                "team": record.assigned_team.value,
                "human_review_required": record.human_review_required,
                "model": record.model_name,
                "prompt_version": record.prompt_version,
                "latency_ms": record.processing_latency_ms,
                "retrieved_chunks": len(result.retrieved),
                "demo_mode": record.demo_mode,
                "fallback_used": result.fallback_used,
            },
        )

    @staticmethod
    def _create_task(
        conversation: Conversation, record: AIAnalysis, result: PipelineResult
    ) -> Task | None:
        if result.action.recommended_action == RecommendedAction.NO_ACTION:
            return None

        priority = {
            Urgency.CRITICAL: TaskPriority.CRITICAL,
            Urgency.HIGH: TaskPriority.HIGH,
            Urgency.MEDIUM: TaskPriority.MEDIUM,
            Urgency.LOW: TaskPriority.LOW,
        }[result.rules.urgency]

        task = Task(
            customer_id=conversation.customer_id,
            conversation_id=conversation.id,
            ai_analysis_id=record.id,
            title=(
                f"{result.action.recommended_action.value.replace('_', ' ').title()} - "
                f"{conversation.customer.full_name}"
            ),
            description=result.action.reason,
            assigned_team=result.action.assign_to,
            priority=priority,
            status=TaskStatus.OPEN,
            due_at=utcnow() + timedelta(hours=result.action.follow_up_hours),
            source="AI_WORKFLOW",
        )
        db.session.add(task)
        db.session.flush()

        record_audit(
            AuditAction.TASK_CREATED,
            entity_type="Task",
            entity_id=task.id,
            metadata={
                "analysis_id": record.id,
                "team": task.assigned_team.value,
                "priority": task.priority.value,
                "due_in_hours": result.action.follow_up_hours,
            },
        )
        return task
