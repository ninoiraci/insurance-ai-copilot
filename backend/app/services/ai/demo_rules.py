"""Deterministic Spanish rule engine used by DEMO MODE.

This is **not** AI. It is a keyword/regex baseline that produces the same JSON
contract a real model would, so the whole application - pipeline, persistence,
UI, evaluation - stays demonstrable with no API key and no network.

Keeping it in its own module has a second benefit: it is a genuine *baseline*
to evaluate the LLM against. If an expensive model cannot beat a keyword
matcher on this taxonomy, that is worth knowing.
"""

from __future__ import annotations

import re
import unicodedata

from ...models.enums import (
    ACTION_TO_TEAM,
    InsuranceType,
    Intent,
    RecommendedAction,
    Urgency,
)


def fold(text: str) -> str:
    """Lowercase and strip accents so 'matrícula' matches 'matricula'."""
    lowered = text.lower()
    decomposed = unicodedata.normalize("NFD", lowered)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


# Ordered: the first intent to reach a score wins ties by list position, which
# encodes business priority (a complaint about a claim is still a complaint).
INTENT_RULES: tuple[tuple[Intent, tuple[str, ...]], ...] = (
    (
        Intent.COMPLAINT,
        (
            "queja", "reclamacion formal", "hoja de reclamaciones", "inaceptable",
            "vergonzoso", "defensor del asegurado", "muy descontento", "indignado",
            "tomare medidas", "denunciar", "pesimo servicio", "llevo semanas sin",
        ),
    ),
    (
        Intent.CANCELLATION,
        (
            "dar de baja", "darme de baja", "cancelar la poliza", "cancelar el seguro",
            "anular la poliza", "no quiero renovar", "no renovar", "no deseo renovar",
            "no deseo que se renueve", "rescindir", "baja del seguro", "quiero cancelar",
            "causar baja", "solicito dar de baja", "quiero anular", "anular el seguro",
        ),
    ),
    (
        Intent.CLAIM,
        (
            "siniestro", "accidente", "he tenido un golpe", "tuve un golpe", "choque",
            "colision", "me han dado", "parte amistoso", "robo", "robar", "robado",
            "gotera", "fuga de agua", "escape de agua", "incendio", "granizo",
            "inundado", "inundacion", "rotura de", "dano", "danos", "atropello",
            "herido", "heridos", "grua", "averia", "cristal roto", "luna rota",
            "tuberia rota", "se ha estropeado", "perdio mi maleta", "extravio",
        ),
    ),
    (
        Intent.PAYMENT,
        (
            "recibo", "cobro", "devuelto", "domiciliacion", "impagado", "impago",
            "cargo duplicado", "no me han cobrado", "pagar", "cuota", "fraccionar",
            "cambiar la cuenta", "numero de cuenta", "iban",
        ),
    ),
    (
        Intent.RENEWAL,
        (
            "renovar", "renovacion", "vence", "caduca", "se acaba mi seguro",
            "expira", "vencimiento", "renueva",
        ),
    ),
    (
        Intent.NEW_QUOTE,
        (
            "presupuesto", "cuanto costaria", "cuanto cuesta", "precio",
            "quiero contratar", "me gustaria contratar", "cotizar", "tarifa",
            "oferta para", "asegurar mi", "dar de alta un seguro",
        ),
    ),
    (
        Intent.DOCUMENT_REQUEST,
        (
            "que documentacion", "que documentos", "necesito enviar",
            "podeis enviarme", "copia de la poliza", "certificado", "recibo en pdf",
            "documentacion necesito", "papeles",
        ),
    ),
    (
        Intent.POLICY_CHANGE,
        (
            "cambiar de domicilio", "cambio de direccion", "nueva direccion", "me he mudado",
            "anadir", "conductora", "conductor ocasional", "incluir a", "modificar la poliza",
            "actualizar mis datos", "actualizar la direccion", "he cambiado de vehiculo",
            "cambiar el vehiculo", "ampliar la cobertura", "quitar la cobertura",
        ),
    ),
    (
        Intent.POLICY_INFORMATION,
        (
            "cubre", "cobertura", "esta incluido", "incluye", "mi poliza",
            "condiciones", "franquicia", "que entra en", "tengo cubierto",
        ),
    ),
    (
        Intent.CROSS_SELL,
        (
            "ademas del seguro", "ya tengo con vosotros", "aprovechando que",
            "tambien me interesa", "otro seguro con vosotros",
        ),
    ),
)

INSURANCE_RULES: tuple[tuple[InsuranceType, tuple[str, ...]], ...] = (
    (
        InsuranceType.MOTOR,
        (
            "coche", "vehiculo", "matricula", "moto", "motocicleta", "furgoneta",
            "conductor", "carnet", "itv", "parachoques", "paragolpes", "retrovisor",
            "grua", "luna", "atropello", "seguro del coche", "a terceros", "todo riesgo",
        ),
    ),
    (
        InsuranceType.HOME,
        (
            "hogar", "casa", "piso", "vivienda", "gotera", "tuberia", "comunidad",
            "inquilino", "electrodomestico", "caldera", "persiana", "cerradura",
            "seguro del hogar", "inmueble", "garaje",
        ),
    ),
    (
        InsuranceType.HEALTH,
        (
            "salud", "medico", "dentista", "hospital", "consulta", "especialista",
            "cuadro medico", "pediatra", "urgencias medicas", "fisioterapia",
        ),
    ),
    (
        InsuranceType.LIFE,
        ("seguro de vida", "fallecimiento", "beneficiario", "invalidez", "decesos"),
    ),
    (
        InsuranceType.TRAVEL,
        (
            "viaje", "vuelo", "equipaje", "extranjero", "maleta", "cancelacion del vuelo",
            "seguro de viaje", "vacaciones",
        ),
    ),
    (
        InsuranceType.BUSINESS,
        (
            "negocio", "empresa", "comercio", "local", "autonomo", "responsabilidad civil",
            "nave industrial", "mi tienda", "actividad profesional",
        ),
    ),
)

# Signals that a person may be hurt. Deliberately broad: a false positive costs
# a human review, a false negative costs a delayed emergency.
INJURY_TERMS = (
    "herido", "heridos", "herida", "lesion", "lesiones", "ambulancia",
    "hospital", "urgencias", "me duele", "dolor de cuello", "cervical",
    "fractura", "sangre", "inconsciente", "atropell",
)
NO_INJURY_TERMS = (
    "no hubo heridos", "sin heridos", "nadie resulto herido", "no hay heridos",
    "por suerte nadie", "solo danos materiales", "sin lesiones",
)
EMERGENCY_TERMS = (
    "urgente", "emergencia", "ahora mismo", "estoy en la carretera", "sin luz",
    "sin agua", "no puedo entrar", "inundacion", "incendio", "se esta inundando",
    "estoy tirado", "no arranca en plena",
)
THIRD_PARTY_TERMS = (
    "otro coche", "otro vehiculo", "el otro conductor", "tercero", "terceros",
    "me dio", "me golpeo", "el contrario",
)

VAGUE_TERMS = (
    "no me funciona", "no va", "tengo un problema", "hola", "una duda",
    "necesito ayuda", "que tal", "informacion",
)

# Markers emitted by the prompt renderer that DEMO MODE reads back. They are
# formats this project owns, unlike the prose of the prompts themselves.
CUSTOMER_MESSAGE_RE = re.compile(
    r"<<<CUSTOMER_MESSAGE_START(.*?)CUSTOMER_MESSAGE_END>>>", re.DOTALL
)
SOURCE_CITATION_RE = re.compile(r"\[Source:\s*(.+?)\]")

PLATE_RE = re.compile(r"\b(\d{4})\s?-?\s?([A-Za-z]{3})\b")
POLICY_RE = re.compile(r"\b((?:MOT|HOM|LIF|HEA|TRV|BUS)-\d{5})\b", re.IGNORECASE)
AMOUNT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:€|euros?|eur\b)", re.IGNORECASE)
ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
ES_DATE_RE = re.compile(
    r"\b(\d{1,2})\s*(?:de\s*)?"
    r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|"
    r"noviembre|diciembre)\b",
    re.IGNORECASE,
)
RELATIVE_DATE_TERMS = (
    "ayer", "anteayer", "hoy", "esta manana", "esta noche", "anoche",
    "el fin de semana", "la semana pasada", "el sabado", "el domingo",
    "el viernes", "el lunes", "el martes", "el miercoles", "el jueves",
)

# Baseline urgency by intent, before the deterministic rule engine adjusts it.
BASE_URGENCY: dict[Intent, Urgency] = {
    Intent.CLAIM: Urgency.MEDIUM,
    Intent.COMPLAINT: Urgency.HIGH,
    Intent.CANCELLATION: Urgency.MEDIUM,
    Intent.PAYMENT: Urgency.MEDIUM,
    Intent.RENEWAL: Urgency.LOW,
    Intent.NEW_QUOTE: Urgency.LOW,
    Intent.DOCUMENT_REQUEST: Urgency.LOW,
    Intent.POLICY_INFORMATION: Urgency.LOW,
    Intent.POLICY_CHANGE: Urgency.LOW,
    Intent.CROSS_SELL: Urgency.LOW,
    Intent.GENERAL_SUPPORT: Urgency.LOW,
    Intent.UNKNOWN: Urgency.MEDIUM,
}

INTENT_ACTION: dict[Intent, RecommendedAction] = {
    Intent.CLAIM: RecommendedAction.CREATE_CLAIM_CASE,
    Intent.COMPLAINT: RecommendedAction.ESCALATE_TO_HUMAN,
    Intent.CANCELLATION: RecommendedAction.CANCELLATION_WORKFLOW,
    Intent.PAYMENT: RecommendedAction.ASSIGN_TO_ADMIN,
    Intent.RENEWAL: RecommendedAction.RENEWAL_CONTACT,
    Intent.NEW_QUOTE: RecommendedAction.PREPARE_QUOTE,
    Intent.DOCUMENT_REQUEST: RecommendedAction.SEND_POLICY_INFORMATION,
    Intent.POLICY_INFORMATION: RecommendedAction.SEND_POLICY_INFORMATION,
    Intent.POLICY_CHANGE: RecommendedAction.ASSIGN_TO_ADMIN,
    Intent.CROSS_SELL: RecommendedAction.ASSIGN_TO_SALES,
    Intent.GENERAL_SUPPORT: RecommendedAction.REQUEST_CLARIFICATION,
    Intent.UNKNOWN: RecommendedAction.REQUEST_CLARIFICATION,
}

# Facts a human needs before each intent can be actioned, keyed by the entity
# that would satisfy them.
REQUIRED_FACTS: dict[Intent, tuple[tuple[str, str], ...]] = {
    Intent.CLAIM: (
        ("incident_date", "incident date"),
        ("incident_location", "incident location"),
        ("third_party_involved", "third party involvement"),
        ("policy_number", "policy number"),
    ),
    Intent.PAYMENT: (("policy_number", "policy number"),),
    Intent.CANCELLATION: (
        ("policy_number", "policy number"),
        ("cancellation_reason", "cancellation reason"),
    ),
    Intent.NEW_QUOTE: (("quote_details", "risk details for the quote"),),
    Intent.POLICY_CHANGE: (("policy_number", "policy number"),),
}


# Intent precedence, taken directly from the internal escalation procedure
# (09_escalation_rules.md, section 4: "Un mensaje que contiene una queja y una
# consulta comercial se trata como queja"). Without this, a cancellation phrased
# as "no deseo renovarla" scores more RENEWAL keywords than CANCELLATION ones
# and silently loses its mandatory human review.
INTENT_SUPPRESSES: dict[Intent, frozenset[Intent]] = {
    Intent.COMPLAINT: frozenset(
        {Intent.CLAIM, Intent.PAYMENT, Intent.RENEWAL, Intent.POLICY_INFORMATION}
    ),
    Intent.CANCELLATION: frozenset({Intent.RENEWAL, Intent.POLICY_CHANGE}),
    Intent.CLAIM: frozenset({Intent.DOCUMENT_REQUEST}),
}


def _count_hits(folded: str, keywords: tuple[str, ...]) -> list[str]:
    return [keyword for keyword in keywords if keyword in folded]


def classify_intent(folded: str) -> tuple[Intent, list[str]]:
    scores: dict[Intent, list[str]] = {}
    for intent, keywords in INTENT_RULES:
        hits = _count_hits(folded, keywords)
        if hits:
            scores[intent] = hits

    if not scores:
        if any(term in folded for term in VAGUE_TERMS):
            return Intent.GENERAL_SUPPORT, []
        return Intent.UNKNOWN, []

    suppressed: set[Intent] = set()
    for intent in scores:
        suppressed |= INTENT_SUPPRESSES.get(intent, frozenset())

    eligible = {
        intent: hits for intent, hits in scores.items() if intent not in suppressed
    } or scores

    # Most keyword hits wins. INTENT_RULES is ordered by business priority, so
    # walking it in order means ties resolve to the higher-priority intent.
    best_intent, best_hits = Intent.UNKNOWN, []
    for intent, _ in INTENT_RULES:
        hits = eligible.get(intent, [])
        if len(hits) > len(best_hits):
            best_intent, best_hits = intent, hits

    return best_intent, best_hits


def classify_insurance(folded: str) -> tuple[InsuranceType, list[str]]:
    best_type, best_hits = InsuranceType.UNKNOWN, []
    for insurance_type, keywords in INSURANCE_RULES:
        hits = _count_hits(folded, keywords)
        if len(hits) > len(best_hits):
            best_type, best_hits = insurance_type, hits
    return best_type, best_hits


def extract_entities(raw: str, folded: str) -> dict:
    entities: dict[str, object] = {}

    plate = PLATE_RE.search(raw)
    if plate:
        entities["vehicle_plate"] = f"{plate.group(1)}{plate.group(2).upper()}"

    policy = POLICY_RE.search(raw)
    if policy:
        entities["policy_number"] = policy.group(1).upper()

    iso = ISO_DATE_RE.search(raw)
    if iso:
        entities["incident_date"] = iso.group(1)
    else:
        spanish = ES_DATE_RE.search(raw)
        if spanish:
            entities["incident_date"] = spanish.group(0)
        else:
            for term in RELATIVE_DATE_TERMS:
                if term in folded:
                    entities["incident_date"] = term
                    break

    amount = AMOUNT_RE.search(raw)
    if amount:
        entities["amount"] = float(amount.group(1).replace(".", "").replace(",", "."))

    if any(term in folded for term in NO_INJURY_TERMS):
        entities["injuries"] = False
    elif any(term in folded for term in INJURY_TERMS):
        entities["injuries"] = True

    if any(term in folded for term in THIRD_PARTY_TERMS):
        entities["third_party_involved"] = True

    location = re.search(
        r"\b(?:en|cerca de|a la altura de)\s+(?:la\s+|el\s+)?"
        r"((?:calle|avenida|carretera|autopista|autovia|plaza|rotonda|parking|"
        r"garaje|A-\d+|M-\d+|N-\d+)[^.,;\n]{0,60})",
        raw,
        re.IGNORECASE,
    )
    if location:
        entities["incident_location"] = location.group(1).strip()

    damage = re.search(
        r"\b(paragolpes|parachoques|retrovisor|luna|puerta|aleta|capo|rueda|"
        r"tuberia|techo|pared|suelo|ventana|persiana)\b[^.,;\n]{0,40}",
        folded,
    )
    if damage:
        entities["damage_description"] = damage.group(0).strip()

    return entities


def derive_missing_information(intent: Intent, entities: dict, folded: str) -> list[str]:
    missing: list[str] = []
    for key, label in REQUIRED_FACTS.get(intent, ()):
        if key in entities:
            continue
        if key == "cancellation_reason" and any(
            term in folded for term in ("porque", "ya que", "motivo", "he vendido")
        ):
            continue
        if key == "quote_details" and len(folded) > 220:
            continue
        missing.append(label)

    if intent == Intent.CLAIM:
        if not any(term in folded for term in ("foto", "imagen", "adjunto", "te envio")):
            missing.append("accident photographs")
        if entities.get("third_party_involved") and "parte amistoso" not in folded:
            missing.append("signed accident statement")
    return missing[:6]


def score_confidence(
    intent: Intent, intent_hits: list[str], insurance_hits: list[str], folded: str
) -> float:
    if intent == Intent.UNKNOWN:
        return 0.28
    if intent == Intent.GENERAL_SUPPORT and not intent_hits:
        return 0.35

    confidence = 0.55 + 0.10 * min(len(intent_hits), 3) + 0.05 * min(len(insurance_hits), 2)
    if len(folded) < 40:
        confidence -= 0.12  # very short messages carry little evidence
    if any(term in folded for term in VAGUE_TERMS) and len(intent_hits) < 2:
        confidence -= 0.10
    if "?" in folded and intent in {Intent.POLICY_INFORMATION, Intent.DOCUMENT_REQUEST}:
        confidence += 0.05
    return round(max(0.20, min(confidence, 0.93)), 2)


def analyse(message: str) -> dict:
    """Produce a `MessageAnalysis`-shaped dict from a raw Spanish message."""
    raw = message or ""
    folded = fold(raw)

    intent, intent_hits = classify_intent(folded)
    insurance_type, insurance_hits = classify_insurance(folded)
    entities = extract_entities(raw, folded)
    missing = derive_missing_information(intent, entities, folded)
    confidence = score_confidence(intent, intent_hits, insurance_hits, folded)

    # Urgency here is only the *baseline the message supports*. Escalation for
    # injuries, emergencies and policy state is owned exclusively by
    # services/workflows/business_rules.py - duplicating it here would mean two
    # places to change when the business changes its mind.
    urgency = BASE_URGENCY.get(intent, Urgency.MEDIUM)
    if any(term in folded for term in EMERGENCY_TERMS):
        urgency = Urgency.max(urgency, Urgency.HIGH)

    action = INTENT_ACTION.get(intent, RecommendedAction.ESCALATE_TO_HUMAN)
    if intent == Intent.CLAIM and missing:
        action = RecommendedAction.REQUEST_DOCUMENTS

    summary = _summarise(intent, insurance_type, entities, raw)

    return {
        "intent": intent.value,
        "insurance_type": insurance_type.value,
        "urgency": urgency.value,
        "confidence": confidence,
        "summary": summary,
        "extracted_entities": entities,
        "missing_information": missing,
        "recommended_action": action.value,
        "assigned_team": ACTION_TO_TEAM[action].value,
        "human_review_required": True,
        "reasoning": (
            f"Demo rule engine matched {len(intent_hits)} intent keyword(s) "
            f"and {len(insurance_hits)} product keyword(s)."
        ),
    }


def _summarise(
    intent: Intent, insurance_type: InsuranceType, entities: dict, raw: str
) -> str:
    label = {
        Intent.CLAIM: "reports an incident",
        Intent.RENEWAL: "asks about renewing a policy",
        Intent.NEW_QUOTE: "requests a quote",
        Intent.PAYMENT: "raises a payment issue",
        Intent.DOCUMENT_REQUEST: "requests documentation",
        Intent.POLICY_INFORMATION: "asks about policy coverage",
        Intent.POLICY_CHANGE: "requests a policy change",
        Intent.CANCELLATION: "requests cancellation",
        Intent.COMPLAINT: "raises a complaint",
        Intent.CROSS_SELL: "shows interest in an additional product",
        Intent.GENERAL_SUPPORT: "sends a general enquiry",
        Intent.UNKNOWN: "sends an unclear message",
    }[intent]

    product = "" if insurance_type == InsuranceType.UNKNOWN else f" ({insurance_type.value})"
    details = []
    if entities.get("vehicle_plate"):
        details.append(f"plate {entities['vehicle_plate']}")
    if entities.get("incident_date"):
        details.append(f"date '{entities['incident_date']}'")
    if entities.get("injuries") is True:
        details.append("possible injuries reported")
    elif entities.get("injuries") is False:
        details.append("no injuries reported")

    suffix = f" Details: {', '.join(details)}." if details else ""
    excerpt = raw.strip().replace("\n", " ")[:90]
    return f"Customer {label}{product}.{suffix} Message opens: \"{excerpt}\"".strip()
