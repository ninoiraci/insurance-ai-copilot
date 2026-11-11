"""DEMO MODE provider: a drop-in `LLMProvider` backed by deterministic rules.

It receives exactly what a real provider receives - a rendered system prompt
and a rendered user prompt - and returns the same JSON contract. Nothing
downstream knows the difference, except that `is_demo` is True and every
analysis it produces is flagged `demo_mode` in the database and labelled
"Demo AI Mode" in the UI.

We are explicit about this being a mock. It exists so the project can be run
and reviewed with no API key, not to pass itself off as a model.

## How it reads the prompt

A provider only ever sees two strings, so the mock has to recover a little
structure from them. It reads exactly **two machine-readable markers** that the
prompt renderer emits and this project owns:

* `<<<CUSTOMER_MESSAGE_START ... CUSTOMER_MESSAGE_END>>>` - the customer text
* `[Source: <citation>]` - the retrieved knowledge chunks

Everything else it needs (intent, missing information) it derives by running
the same `demo_rules.analyse()` over the extracted message. It deliberately
does not parse the prose of the prompt: keying off an English sentence like
"Missing information we need from the customer" would silently break the demo
the first time someone reworded the prompt.
"""

from __future__ import annotations

import json
import time

from ...models.enums import Intent
from .base import LLMProvider, LLMResponse
from .demo_rules import CUSTOMER_MESSAGE_RE, SOURCE_CITATION_RE, analyse

BROKERAGE = "Correduría Ejemplo"

# Spanish phrasing for the English `missing_information` labels the rule engine
# produces. Anything unmapped falls through to the label itself.
MISSING_INFO_ES = {
    "incident date": "la fecha exacta del siniestro",
    "incident location": "el lugar donde ocurrió",
    "third party involvement": "si hubo terceros implicados",
    "policy number": "el número de su póliza",
    "accident photographs": "fotografías de los daños",
    "signed accident statement": "el parte amistoso firmado",
    "cancellation reason": "el motivo de la baja",
    "risk details for the quote": "los datos del riesgo a asegurar",
}

INTRO_ES = {
    Intent.CLAIM: (
        "Lamentamos lo ocurrido. Hemos abierto el expediente de siniestro y nuestro "
        "departamento correspondiente lo tramitará según el procedimiento habitual."
    ),
    Intent.RENEWAL: (
        "Gracias por ponerse en contacto con nosotros respecto a la renovación de su "
        "póliza. Revisaremos las condiciones vigentes y le confirmaremos las opciones "
        "disponibles."
    ),
    Intent.PAYMENT: (
        "Hemos tomado nota de la incidencia con el recibo. Nuestro departamento de "
        "administración la revisará y le confirmará los pasos a seguir."
    ),
    Intent.CANCELLATION: (
        "Hemos registrado su solicitud de baja. Le confirmaremos los plazos y "
        "requisitos aplicables antes de tramitarla."
    ),
    Intent.COMPLAINT: (
        "Lamentamos la situación descrita. Su caso ha sido escalado para una revisión "
        "prioritaria y recibirá respuesta de un responsable."
    ),
    Intent.NEW_QUOTE: (
        "Gracias por su interés. Prepararemos un presupuesto ajustado a sus necesidades."
    ),
    Intent.DOCUMENT_REQUEST: (
        "Con mucho gusto le indicamos la documentación aplicable según nuestro "
        "procedimiento interno."
    ),
    Intent.POLICY_INFORMATION: (
        "Le confirmamos la información general según nuestros procedimientos. Las "
        "condiciones concretas de su póliza se las confirmará un asesor."
    ),
    Intent.POLICY_CHANGE: (
        "Hemos registrado su solicitud de modificación y la trasladamos al departamento "
        "de administración."
    ),
}

HOLDING_REPLY = (
    "Estimado/a cliente:\n\n"
    "Hemos recibido su mensaje y lo estamos revisando. Para poder darle una respuesta "
    "fiable, un miembro de nuestro equipo se pondrá en contacto con usted a la mayor "
    "brevedad.\n\n"
    "Gracias por su paciencia.\n\n"
    f"El equipo de {BROKERAGE}"
)

NO_KNOWLEDGE_REPLY = (
    "No dispongo de información suficiente en la base de conocimiento para responder "
    "a esta consulta de forma fiable."
)


class DemoProvider(LLMProvider):
    name = "demo"

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("model", "demo-rule-engine-v1")
        kwargs.setdefault("temperature", 0.0)
        kwargs.setdefault("max_tokens", 0)
        kwargs.setdefault("timeout", 0)
        super().__init__(**kwargs)

    @property
    def is_demo(self) -> bool:
        return True

    def complete(self, system: str, user: str) -> LLMResponse:
        started = time.perf_counter()
        payload = self._build_payload(system, user)

        # A small synthetic delay keeps latency charts from being all zeros and
        # makes the "AI is working" state visible in the UI.
        time.sleep(0.04)
        return LLMResponse(
            text=json.dumps(payload, ensure_ascii=False),
            model=self.model,
            latency_ms=int((time.perf_counter() - started) * 1000),
            token_usage={"input_tokens": 0, "output_tokens": 0},
            is_demo=True,
        )

    def _build_payload(self, system: str, user: str) -> dict:
        """Pick a response shape from the contract the prompt declares.

        Three prompts, two contracts:
          classification_v1 -> MessageAnalysis
          response_v1       -> GeneratedResponse, has a customer message
          rag_answer_v1     -> GeneratedResponse, has no customer message
        """
        message_match = CUSTOMER_MESSAGE_RE.search(user)
        wants_response = '"response_text"' in system

        if not wants_response:
            message = message_match.group(1).strip() if message_match else user.strip()
            return analyse(message)

        sources = SOURCE_CITATION_RE.findall(user)
        if message_match is None:
            return self._internal_answer(user, sources)
        return self._customer_reply(message_match.group(1).strip(), sources)

    def _customer_reply(self, message: str, sources: list[str]) -> dict:
        # Re-derive intent and gaps from the message itself rather than from the
        # prompt's prose. Same rule engine, so the reply always agrees with the
        # classification the pipeline already stored.
        analysis = analyse(message)
        intent = Intent.coerce(analysis["intent"], Intent.UNKNOWN)
        missing = analysis["missing_information"]

        if not sources and intent not in {Intent.GENERAL_SUPPORT, Intent.UNKNOWN}:
            return {
                "response_text": HOLDING_REPLY,
                "used_sources": [],
                "grounded": False,
                "insufficient_information": True,
            }

        intro = INTRO_ES.get(
            intent,
            "Gracias por su mensaje. Para poder ayudarle correctamente necesitamos "
            "algún detalle adicional.",
        )
        body = intro
        if missing:
            bullets = "\n".join(f"• {MISSING_INFO_ES.get(item, item)}" for item in missing)
            body = f"{intro}\n\nPara continuar necesitamos:\n{bullets}"

        return {
            "response_text": (
                f"Estimado/a cliente:\n\n{body}\n\n"
                "Quedamos a su disposición para cualquier aclaración.\n\n"
                f"El equipo de {BROKERAGE}"
            ),
            "used_sources": sources[:4],
            "grounded": bool(sources),
            "insufficient_information": not sources,
        }

    @staticmethod
    def _internal_answer(user: str, sources: list[str]) -> dict:
        """RAG Playground answer: quote the retrieved text, never paraphrase.

        The mock cannot summarise, and inventing a summary would misrepresent
        what the retrieval layer actually returned.
        """
        if not sources:
            return {
                "response_text": NO_KNOWLEDGE_REPLY,
                "used_sources": [],
                "grounded": False,
                "insufficient_information": True,
            }

        excerpt = user.split("[Source:")[1].split("]", 1)[1].strip()[:700]
        return {
            "response_text": (
                "Según la base de conocimiento interna, el fragmento más relevante es:\n\n"
                f"{excerpt}\n\n"
                "(Modo demo: el texto se cita literalmente, no se resume con un modelo.)"
            ),
            "used_sources": sources[:4],
            "grounded": True,
            "insufficient_information": False,
        }
