"""Synthetic demo data seeding.

Everything here is invented. No real person, policy, vehicle or claim is
represented. Names are common Spanish names attached to fictional records.

The seed is deterministic (fixed RNG seed) so that a demo shown twice looks
the same, and so tests can rely on the fixture set. It is also idempotent:
re-running updates rather than duplicating.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

from app.extensions import db
from app.models import (
    Channel,
    Conversation,
    ConversationStatus,
    Customer,
    EvaluationCase,
    InsuranceType,
    Intent,
    Message,
    Policy,
    PolicyStatus,
    RecommendedAction,
    SenderType,
    Task,
    TaskPriority,
    TaskStatus,
    Team,
    Urgency,
    utcnow,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
RNG_SEED = 20240115

# 20 synthetic customers. City is used only to make the UI feel real.
CUSTOMERS: list[dict] = [
    {"full_name": "Carlos García Ruiz", "city": "Madrid"},
    {"full_name": "Ana López Moreno", "city": "Valencia"},
    {"full_name": "Pedro Martínez Gil", "city": "Sevilla"},
    {"full_name": "Lucía Fernández Blanco", "city": "Bilbao"},
    {"full_name": "Javier Ruiz Ortega", "city": "Zaragoza"},
    {"full_name": "Marta Sánchez Vidal", "city": "Madrid"},
    {"full_name": "Diego Torres Ibáñez", "city": "Málaga"},
    {"full_name": "Elena Navarro Prieto", "city": "Barcelona"},
    {"full_name": "Sergio Ramos Delgado", "city": "Murcia"},
    {"full_name": "Beatriz Molina Cano", "city": "Valladolid"},
    {"full_name": "Alberto Castro Nieto", "city": "Alicante"},
    {"full_name": "Cristina Herrera Pardo", "city": "Granada"},
    {"full_name": "Raúl Domínguez Vega", "city": "Vigo"},
    {"full_name": "Silvia Márquez Rubio", "city": "Santander"},
    {"full_name": "Óscar Peña Lorenzo", "city": "Salamanca"},
    {"full_name": "Nuria Gallego Ferrer", "city": "Palma"},
    {"full_name": "Iván Serrano Cabrera", "city": "Córdoba"},
    {"full_name": "Patricia Vargas Soler", "city": "Gijón"},
    {"full_name": "Tomás Escobar Rivas", "city": "Toledo"},
    {"full_name": "Rocío Bermúdez Lara", "city": "Cádiz"},
]

PROVIDERS = ("Aseguradora Norte", "Mutua Levante", "Seguros Atlántico", "Iberia Protect")

POLICY_PREFIX = {
    InsuranceType.MOTOR: "MOT",
    InsuranceType.HOME: "HOM",
    InsuranceType.LIFE: "LIF",
    InsuranceType.HEALTH: "HEA",
    InsuranceType.TRAVEL: "TRV",
    InsuranceType.BUSINESS: "BUS",
}

# Conversation templates for the bulk (non-demo) inbox volume. Each is a
# realistic Spanish exchange; the seed picks customers and dates around them.
CONVERSATION_TEMPLATES: list[dict] = [
    {
        "subject": "Consulta sobre cobertura de lunas",
        "channel": Channel.WHATSAPP,
        "messages": [
            ("CUSTOMER", "Hola, ¿mi póliza cubre la rotura de la luna delantera?"),
            ("AGENT", "Buenos días. Lo comprobamos y le confirmamos en breve."),
        ],
    },
    {
        "subject": "Presupuesto seguro de moto",
        "channel": Channel.EMAIL,
        "messages": [
            (
                "CUSTOMER",
                "Buenas tardes, me gustaría un presupuesto para asegurar una moto de 125cc. "
                "¿Qué necesitan de mí?",
            ),
        ],
    },
    {
        "subject": "Cambio de domicilio",
        "channel": Channel.EMAIL,
        "messages": [
            (
                "CUSTOMER",
                "Me he mudado. ¿Pueden actualizar la dirección en todas mis pólizas? "
                "La nueva es Calle Mayor 45, 3B.",
            ),
            ("AGENT", "Recibido, tramitamos el suplemento y le confirmamos."),
        ],
    },
    {
        "subject": "Duda sobre franquicia",
        "channel": Channel.WHATSAPP,
        "messages": [
            ("CUSTOMER", "¿Cuál es la franquicia de mi seguro de hogar para daños por agua?"),
        ],
    },
    {
        "subject": "Recibo del seguro",
        "channel": Channel.WHATSAPP,
        "messages": [
            ("CUSTOMER", "¿Cuándo se pasa el recibo este año? Quiero tener saldo suficiente."),
        ],
    },
    {
        "subject": "Siniestro de agua en el baño",
        "channel": Channel.WHATSAPP,
        "messages": [
            (
                "CUSTOMER",
                "Tengo una fuga de agua debajo del lavabo y se ha estropeado el mueble. "
                "¿Cómo lo declaro?",
            ),
            ("AGENT", "Lamentamos lo ocurrido. Le indicamos la documentación necesaria."),
            ("CUSTOMER", "Perfecto, ya tengo fotos hechas."),
        ],
    },
    {
        "subject": "Alta de seguro de viaje",
        "channel": Channel.EMAIL,
        "messages": [
            (
                "CUSTOMER",
                "Viajo a Tailandia en septiembre durante tres semanas. Necesito un seguro "
                "de viaje con cobertura médica amplia.",
            ),
        ],
    },
    {
        "subject": "Consulta cuadro médico",
        "channel": Channel.PHONE_CALL,
        "messages": [
            (
                "CUSTOMER",
                "Transcripción de llamada: 'Quería saber si el dermatólogo del centro de "
                "la calle Alcalá entra en mi cuadro médico.'",
            ),
        ],
    },
    {
        "subject": "Añadir conductor a la póliza",
        "channel": Channel.WHATSAPP,
        "messages": [
            ("CUSTOMER", "Quiero añadir a mi hijo como conductor ocasional en el seguro del coche."),
            ("AGENT", "De acuerdo, necesitamos su permiso de conducir y fecha de nacimiento."),
        ],
    },
    {
        "subject": "Retraso en la tramitación",
        "channel": Channel.EMAIL,
        "messages": [
            (
                "CUSTOMER",
                "Llevo dos semanas esperando noticias del perito y nadie me ha llamado. "
                "Me gustaría saber en qué punto está mi expediente.",
            ),
        ],
    },
    {
        "subject": "Seguro para el local comercial",
        "channel": Channel.EMAIL,
        "messages": [
            (
                "CUSTOMER",
                "Voy a abrir una peluquería y necesito un multirriesgo de comercio con "
                "responsabilidad civil. ¿Qué tarifas manejan?",
            ),
        ],
    },
    {
        "subject": "Robo en el vehículo",
        "channel": Channel.WHATSAPP,
        "messages": [
            (
                "CUSTOMER",
                "Me han roto la ventanilla del coche y se han llevado la radio. Ya he puesto "
                "la denuncia. Matrícula 4455JHG.",
            ),
        ],
    },
    {
        "subject": "Certificado de seguro",
        "channel": Channel.EMAIL,
        "messages": [
            ("CUSTOMER", "Necesito un certificado de mi seguro de hogar para el banco."),
            ("AGENT", "Se lo enviamos hoy mismo por correo electrónico."),
        ],
    },
    {
        "subject": "Consulta sobre beneficiarios",
        "channel": Channel.PHONE_CALL,
        "messages": [
            (
                "CUSTOMER",
                "Transcripción de llamada: 'Quería revisar quiénes figuran como "
                "beneficiarios en mi seguro de vida y cómo puedo cambiarlos.'",
            ),
        ],
    },
    {
        "subject": "Asistencia en carretera",
        "channel": Channel.WHATSAPP,
        "messages": [
            (
                "CUSTOMER",
                "Estoy tirado en la carretera, el coche no arranca. ¿Me podéis mandar una grúa?",
            ),
        ],
    },
    {
        "subject": "Baja del seguro de moto",
        "channel": Channel.EMAIL,
        "messages": [
            (
                "CUSTOMER",
                "He vendido la moto, quiero dar de baja la póliza y que me devuelvan la "
                "parte proporcional.",
            ),
        ],
    },
]

FOLLOW_UP_AGENT_REPLIES = (
    "Gracias por su mensaje. Lo revisamos y le respondemos a la mayor brevedad.",
    "Hemos registrado su solicitud. Un compañero se pondrá en contacto con usted.",
    "Recibido. Le confirmamos en cuanto tengamos la información de la compañía.",
)

CUSTOMER_FOLLOW_UPS = (
    "Perfecto, muchas gracias por la información.",
    "De acuerdo, quedo a la espera entonces.",
    "Gracias. ¿Sabéis cuánto puede tardar aproximadamente?",
    "Vale, os envío lo que me pedís esta tarde.",
)

TASK_TEMPLATES = (
    ("Revisar renovación pendiente", Team.SALES_TEAM, TaskPriority.MEDIUM),
    ("Solicitar documentación de siniestro", Team.CLAIMS_TEAM, TaskPriority.HIGH),
    ("Regularizar recibo devuelto", Team.ADMIN_TEAM, TaskPriority.HIGH),
    ("Preparar comparativa de mercado", Team.SALES_TEAM, TaskPriority.LOW),
    ("Actualizar datos de contacto", Team.ADMIN_TEAM, TaskPriority.LOW),
    ("Llamada de seguimiento al cliente", Team.CUSTOMER_SUCCESS, TaskPriority.MEDIUM),
)


def _slug(name: str) -> str:
    replacements = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n", "ü": "u"}
    lowered = name.lower()
    for accented, plain in replacements.items():
        lowered = lowered.replace(accented, plain)
    parts = lowered.split()
    return f"{parts[0]}.{parts[1]}" if len(parts) > 1 else parts[0]


def seed_customers(rng: random.Random) -> dict[str, Customer]:
    customers: dict[str, Customer] = {}
    for index, spec in enumerate(CUSTOMERS):
        email = f"{_slug(spec['full_name'])}@example.invalid"
        customer = db.session.query(Customer).filter_by(email=email).one_or_none()
        if customer is None:
            customer = Customer(email=email)
            db.session.add(customer)
        customer.full_name = spec["full_name"]
        customer.city = spec["city"]
        customer.phone = f"+34 6{rng.randint(10, 99)} {rng.randint(100, 999)} {rng.randint(100, 999)}"
        customer.preferred_language = "es"
        customer.created_at = utcnow() - timedelta(days=rng.randint(120, 1400))
        customers[spec["full_name"]] = customer
    db.session.flush()
    return customers


def seed_policies(customers: dict[str, Customer], rng: random.Random) -> int:
    """30+ policies. Specific expiry dates power the demo business rules."""
    today = date.today()

    # Hand-tuned policies that make the demo cases behave as documented.
    scripted: list[tuple[str, InsuranceType, int, PolicyStatus, dict]] = [
        ("Carlos García Ruiz", InsuranceType.MOTOR, 220, PolicyStatus.ACTIVE, {"vehicle_plate": "1234ABC"}),
        ("Carlos García Ruiz", InsuranceType.HOME, 400, PolicyStatus.ACTIVE, {}),
        # DEMO-02: expires in 5 days -> renewal_imminent rule fires.
        ("Ana López Moreno", InsuranceType.MOTOR, 5, PolicyStatus.PENDING_RENEWAL, {"vehicle_plate": "4321BCD"}),
        ("Ana López Moreno", InsuranceType.HEALTH, 310, PolicyStatus.ACTIVE, {}),
        # DEMO-03: expires in 9 days -> payment_close_to_expiry rule fires.
        ("Pedro Martínez Gil", InsuranceType.MOTOR, 9, PolicyStatus.ACTIVE, {"vehicle_plate": "5678CDE"}),
        ("Lucía Fernández Blanco", InsuranceType.HEALTH, 190, PolicyStatus.ACTIVE, {}),
        ("Javier Ruiz Ortega", InsuranceType.MOTOR, 150, PolicyStatus.ACTIVE, {"vehicle_plate": "9012XYZ"}),
        ("Javier Ruiz Ortega", InsuranceType.HOME, 95, PolicyStatus.ACTIVE, {}),
        # DEMO-06: high-risk claim customer.
        ("Marta Sánchez Vidal", InsuranceType.MOTOR, 280, PolicyStatus.ACTIVE, {"vehicle_plate": "7788KLM"}),
        # DEMO-07: cancellation target.
        ("Diego Torres Ibáñez", InsuranceType.HOME, 48, PolicyStatus.ACTIVE, {}),
        ("Diego Torres Ibáñez", InsuranceType.LIFE, 500, PolicyStatus.ACTIVE, {}),
        ("Elena Navarro Prieto", InsuranceType.MOTOR, 260, PolicyStatus.ACTIVE, {"vehicle_plate": "3344FGH"}),
        # A lapsed policy so the payment_on_lapsed_policy rule is reachable.
        ("Sergio Ramos Delgado", InsuranceType.MOTOR, -12, PolicyStatus.LAPSED, {"vehicle_plate": "4455JHG"}),
        ("Sergio Ramos Delgado", InsuranceType.HOME, 330, PolicyStatus.ACTIVE, {}),
    ]

    counters: dict[InsuranceType, int] = {}
    created = 0

    def add_policy(
        customer: Customer,
        policy_type: InsuranceType,
        days_to_expiry: int,
        status: PolicyStatus,
        extra: dict,
    ) -> None:
        nonlocal created
        counters[policy_type] = counters.get(policy_type, 0) + 1
        number = f"{POLICY_PREFIX[policy_type]}-{counters[policy_type]:05d}"
        policy = db.session.query(Policy).filter_by(policy_number=number).one_or_none()
        if policy is None:
            policy = Policy(policy_number=number)
            db.session.add(policy)
            created += 1
        expiration = today + timedelta(days=days_to_expiry)
        policy.customer_id = customer.id
        policy.policy_type = policy_type
        policy.provider = rng.choice(PROVIDERS)
        policy.start_date = expiration - timedelta(days=365)
        policy.expiration_date = expiration
        policy.status = status
        policy.annual_premium = round(rng.uniform(180, 1250), 2)
        policy.vehicle_plate = extra.get("vehicle_plate")
        policy.property_address = extra.get("property_address")
        if policy_type == InsuranceType.HOME and not policy.property_address:
            policy.property_address = f"Calle {rng.choice(('Mayor', 'Real', 'Nueva'))} {rng.randint(1, 90)}, {customer.city}"

    for name, policy_type, days, status, extra in scripted:
        add_policy(customers[name], policy_type, days, status, extra)

    # Fill out the remaining customers so every one has at least one policy.
    remaining = [
        customer
        for name, customer in customers.items()
        if not any(spec[0] == name for spec in scripted)
    ]
    for customer in remaining:
        for policy_type in rng.sample(list(POLICY_PREFIX), rng.randint(1, 3)):
            add_policy(
                customer,
                policy_type,
                rng.randint(20, 400),
                PolicyStatus.ACTIVE,
                {"vehicle_plate": f"{rng.randint(1000, 9999)}{''.join(rng.sample('BCDFGHJKLMNPRSTVWXYZ', 3))}"}
                if policy_type == InsuranceType.MOTOR
                else {},
            )

    db.session.flush()
    return created


def seed_conversations(customers: dict[str, Customer], rng: random.Random) -> tuple[int, int]:
    """Load the 8 scripted demo cases, then generate bulk inbox volume."""
    conversations = 0
    messages = 0

    demo_payload = json.loads(
        (DATA_DIR / "synthetic_cases" / "demo_cases.json").read_text(encoding="utf-8")
    )
    for case in demo_payload["cases"]:
        conversation = (
            db.session.query(Conversation).filter_by(reference=case["reference"]).one_or_none()
        )
        if conversation is None:
            conversation = Conversation(reference=case["reference"])
            db.session.add(conversation)
            conversations += 1
        else:
            conversation.messages.clear()

        customer = customers[case["customer"]]
        conversation.customer_id = customer.id
        conversation.channel = Channel(case["channel"])
        conversation.subject = case["subject"]
        conversation.status = ConversationStatus(case["status"])
        conversation.assigned_team = Team.UNASSIGNED

        first_ts = utcnow()
        for entry in case["messages"]:
            timestamp = utcnow() - timedelta(hours=entry["hours_ago"])
            first_ts = min(first_ts, timestamp)
            conversation.messages.append(
                Message(
                    sender_type=SenderType(entry["sender_type"]),
                    content=entry["content"],
                    timestamp=timestamp,
                )
            )
            messages += 1
        conversation.created_at = first_ts
        conversation.updated_at = first_ts

    # Bulk volume: 34 more conversations so the inbox looks like a real desk.
    customer_list = list(customers.values())
    for index in range(34):
        reference = f"CONV-{index + 1:03d}"
        conversation = (
            db.session.query(Conversation).filter_by(reference=reference).one_or_none()
        )
        if conversation is None:
            conversation = Conversation(reference=reference)
            db.session.add(conversation)
            conversations += 1
        else:
            conversation.messages.clear()

        template = CONVERSATION_TEMPLATES[index % len(CONVERSATION_TEMPLATES)]
        customer = customer_list[(index * 7 + 3) % len(customer_list)]
        started = utcnow() - timedelta(days=rng.randint(1, 45), hours=rng.randint(0, 20))

        conversation.customer_id = customer.id
        conversation.channel = template["channel"]
        conversation.subject = template["subject"]
        conversation.status = rng.choice(
            [
                ConversationStatus.NEW,
                ConversationStatus.NEW,
                ConversationStatus.AWAITING_CUSTOMER,
                ConversationStatus.RESOLVED,
            ]
        )
        conversation.assigned_team = Team.UNASSIGNED
        conversation.created_at = started
        conversation.updated_at = started

        offset = 0
        for sender, content in template["messages"]:
            conversation.messages.append(
                Message(
                    sender_type=SenderType(sender),
                    content=content,
                    timestamp=started + timedelta(minutes=offset),
                )
            )
            messages += 1
            offset += rng.randint(20, 300)

        # Most threads continue past the template so the inbox has realistic
        # multi-turn history rather than one message per conversation.
        if index % 3 != 2:
            conversation.messages.append(
                Message(
                    sender_type=SenderType.AGENT,
                    content=rng.choice(FOLLOW_UP_AGENT_REPLIES),
                    timestamp=started + timedelta(minutes=offset + 45),
                )
            )
            messages += 1
        if index % 2 == 0:
            conversation.messages.append(
                Message(
                    sender_type=SenderType.CUSTOMER,
                    content=rng.choice(CUSTOMER_FOLLOW_UPS),
                    timestamp=started + timedelta(minutes=offset + 120),
                )
            )
            messages += 1
        if index % 5 == 0:
            conversation.messages.append(
                Message(
                    sender_type=SenderType.AGENT,
                    content="Confirmado. Queda registrado en su expediente.",
                    timestamp=started + timedelta(minutes=offset + 210),
                )
            )
            messages += 1

    db.session.flush()
    return conversations, messages


def seed_tasks(customers: dict[str, Customer], rng: random.Random) -> int:
    created = 0
    customer_list = list(customers.values())
    existing = db.session.query(Task).filter_by(source="SEED").count()
    if existing >= 20:
        return 0

    for index in range(20):
        title, team, priority = TASK_TEMPLATES[index % len(TASK_TEMPLATES)]
        customer = customer_list[(index * 5 + 1) % len(customer_list)]
        db.session.add(
            Task(
                customer_id=customer.id,
                conversation_id=None,
                title=f"{title} - {customer.full_name}",
                description="Tarea sintética de ejemplo cargada por el script de seed.",
                assigned_team=team,
                priority=priority,
                status=TaskStatus.OPEN if index % 4 else TaskStatus.DONE,
                due_at=utcnow() + timedelta(days=rng.randint(-3, 20)),
                source="SEED",
            )
        )
        created += 1
    db.session.flush()
    return created


def seed_evaluation_cases() -> int:
    payload = json.loads(
        (DATA_DIR / "evaluation" / "evaluation_cases.json").read_text(encoding="utf-8")
    )
    created = 0
    for spec in payload["cases"]:
        case = (
            db.session.query(EvaluationCase)
            .filter_by(case_key=spec["case_key"])
            .one_or_none()
        )
        if case is None:
            case = EvaluationCase(case_key=spec["case_key"])
            db.session.add(case)
            created += 1
        case.input_text = spec["input_text"]
        case.channel = spec.get("channel", "WHATSAPP")
        case.difficulty = spec.get("difficulty", "STANDARD")
        case.notes = spec.get("notes")
        case.expected_intent = Intent(spec["expected_intent"])
        case.expected_urgency = Urgency(spec["expected_urgency"])
        case.expected_insurance_type = InsuranceType(spec["expected_insurance_type"])
        case.expected_action = RecommendedAction(spec["expected_action"])
        case.expected_entities = spec.get("expected_entities", {})
        case.expects_human_review = spec.get("expects_human_review", True)
    db.session.flush()
    return created


def seed_all() -> dict[str, int]:
    rng = random.Random(RNG_SEED)

    customers = seed_customers(rng)
    policies = seed_policies(customers, rng)
    conversations, messages = seed_conversations(customers, rng)
    tasks = seed_tasks(customers, rng)
    evaluation_cases = seed_evaluation_cases()

    db.session.commit()
    return {
        "customers": len(customers),
        "policies_created": policies,
        "conversations_created": conversations,
        "messages_created": messages,
        "tasks_created": tasks,
        "evaluation_cases_created": evaluation_cases,
    }


if __name__ == "__main__":  # pragma: no cover - convenience entry point
    from app import create_app

    app = create_app()
    with app.app_context():
        db.create_all()
        for key, value in seed_all().items():
            print(f"{key}: {value}")
