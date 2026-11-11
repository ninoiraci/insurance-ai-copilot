"""Grounded response drafting.

Separate from classification on purpose:

* different prompt, different failure modes, different temperature appetite;
* a classification can succeed while drafting fails - the operator still gets
  the structured analysis and routing, just without a draft;
* the draft can be regenerated without re-running extraction.
"""

from __future__ import annotations

import logging

from ...prompts import RESPONSE_PROMPT, get_prompt
from ...models import Urgency
from ...schemas.ai_output import (
    AnalysisFailure,
    GeneratedResponse,
    MessageAnalysis,
)
from ..ai.structured import StructuredLLMClient
from ..rag.retriever import KnowledgeRetriever
from ..rag.vector_store import RetrievedChunk
from .action_engine import ActionDecision
from .context import CustomerContext

logger = logging.getLogger(__name__)

BROKERAGE_NAME = "Correduría Ejemplo"

LANGUAGE_NAMES = {"es": "Spanish", "en": "English", "ca": "Catalan"}

# Used when drafting fails entirely. Honest, safe, and obviously a holding reply.
FALLBACK_RESPONSE = (
    "Estimado/a cliente:\n\n"
    "Hemos recibido su mensaje y lo hemos registrado correctamente. "
    "Un miembro de nuestro equipo lo revisará y se pondrá en contacto con usted "
    "a la mayor brevedad posible.\n\n"
    "Gracias por su confianza.\n\n"
    f"El equipo de {BROKERAGE_NAME}"
)


def generate_response(
    client: StructuredLLMClient,
    *,
    analysis: MessageAnalysis,
    urgency: Urgency,
    action: ActionDecision,
    context: CustomerContext | None,
    retrieved: list[RetrievedChunk],
    message: str,
) -> tuple[GeneratedResponse, int]:
    """Return (response, attempts used). Never raises."""
    prompt = get_prompt(RESPONSE_PROMPT)
    language = LANGUAGE_NAMES.get(
        context.preferred_language if context else "es", "Spanish"
    )

    system, user = prompt.render(
        language=language,
        brokerage_name=BROKERAGE_NAME,
        intent=analysis.intent.value,
        insurance_type=analysis.insurance_type.value,
        urgency=urgency.value,
        summary=analysis.summary,
        missing_information="; ".join(analysis.missing_information) or "none",
        recommended_action=action.recommended_action.value,
        customer_context=context.to_prompt_block() if context else "No customer context.",
        retrieved_knowledge=KnowledgeRetriever.format_for_prompt(retrieved),
        message=message,
    )

    try:
        response, _raw, attempts = client.generate(
            schema=GeneratedResponse, system=system, user=user, label="response_generation"
        )
    except AnalysisFailure as exc:
        logger.error("response_generation_failed error=%s", exc)
        return (
            GeneratedResponse(
                response_text=FALLBACK_RESPONSE,
                used_sources=[],
                grounded=False,
                insufficient_information=True,
            ),
            exc.attempts,
        )

    # Trust but verify: a model can claim grounding it does not have. If there
    # were no retrieved chunks, the draft is not grounded, whatever it says.
    valid_citations = {chunk.citation for chunk in retrieved}
    response.used_sources = [
        source for source in response.used_sources if source in valid_citations
    ]
    if not retrieved:
        response.grounded = False
    elif not response.used_sources:
        # Cited nothing despite having material: treat as ungrounded so the
        # review gate catches it.
        response.grounded = False

    return response, attempts
