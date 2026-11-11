# Insurance Conversation Intelligence — AI Case Copilot

A working proof of concept of an internal tool for a Spanish insurance
brokerage: inbound customer messages from **WhatsApp, email and phone
transcripts** are turned into **structured, routed, auditable cases**, with a
human approving every customer-facing reply.

> **All data in this repository is synthetic.** Customers, policies,
> conversations and procedure manuals are invented for demonstration. No real
> personal data, and no proprietary material from any company, is present.

> 🇮🇹 **Italian documentation:** a translation of the main documents is in
> **[docs/it/](docs/it/00-INDICE.md)**. English remains the source of truth;
> where the two disagree, the code wins.

![Conversation detail: the customer thread, the Customer 360 context and the AI Copilot analysis](docs/screenshots/conversation.png)

---

## 1. Why this project exists

Brokerages drown in unstructured inbound messages. The obvious move — "put a
chatbot on it" — is the wrong one: replies about claims, cancellations and
payments carry legal and financial consequence, and a language model is not a
system of record.

So this project takes the opposite position:

> **The LLM is one component inside a controlled business workflow — never the
> decision engine.**

Concretely, that means the model classifies and extracts, and then
**deterministic code owns every decision that matters**: urgency, routing,
whether a human must sign off. The model's output is validated against a strict
schema before anything touches the database, replies are grounded in retrieved
internal procedures, and nothing reaches a customer without a click.

---

## 2. What it does

Given this WhatsApp message:

> *"Hola, ayer tuve un golpe con el coche. No hubo heridos pero tengo el
> paragolpes roto. Mi matrícula es 1234ABC. ¿Qué tengo que enviaros?"*

the system produces:

| Field | Value |
|---|---|
| Intent | `CLAIM` |
| Insurance type | `MOTOR` |
| Urgency | `MEDIUM` |
| Confidence | 0.93 |
| Extracted | plate `1234ABC`, incident date `ayer`, injuries `false`, damage `paragolpes roto` |
| Missing | incident location · third party involvement · policy number · accident photographs |
| Next action | `REQUEST_DOCUMENTS` → `CLAIMS_TEAM`, follow up in 12h |
| Human review | **Required** — high-risk intent |
| Sources | *Procedimiento de Siniestros de Automóvil, §3* · *Documentación Requerida para Siniestros* |
| Draft reply | Professional Spanish response listing the required documents |

…plus a work item for the claims team and a full audit trail.

---

## 3. Key features

- **Structured LLM output** — Pydantic-validated JSON, controlled enums,
  informed retries, safe fallback. An invented label can never reach the database.
- **Deterministic business rules** — injuries force `CRITICAL`; a payment issue
  on a policy expiring in 9 days becomes `HIGH`; complaints are always `HIGH`.
  Rules only ever *raise* urgency, and each override is stored with its reason.
- **Next-best-action engine** — combines classification, customer state,
  urgency and missing information into `action + team + SLA + reason`.
- **RAG over internal procedures** — 10 synthetic manuals, section-aware
  chunking, vector search, and **visible source attribution** on every reply.
- **Human-in-the-loop** — `APPROVE` / `EDIT_AND_APPROVE` / `REJECT`, with both
  the original and final text retained. Nothing is ever auto-sent.
- **Evaluation framework** — 60 labelled cases, per-case results, and a
  **safety metric** (human-review recall on risky cases), runnable from the UI.
- **Audit trail** — every analysis, rule override, safety flag, task and human
  decision, correlated by request ID. Message bodies deliberately excluded.
- **Demo mode** — runs with no API key and no infrastructure, labelled as mock
  everywhere it appears.

---

## 4. Architecture

```mermaid
flowchart LR
    subgraph Channels["Inbound channels (simulated)"]
        WA["WhatsApp"]
        EM["Email"]
        PH["Phone transcript"]
    end

    subgraph FE["Frontend — React + TypeScript + Vite"]
        DASH["Dashboard"]
        INBOX["Unified Inbox"]
        DETAIL["Conversation<br/>Thread · Customer 360 · Copilot"]
        KB["Knowledge Base<br/>+ RAG Playground"]
        EVAL["Evaluations"]
        AUDIT["Audit Logs"]
    end

    subgraph BE["Backend — Flask + SQLAlchemy"]
        API["REST API<br/>blueprints"]
        PIPE["Analysis pipeline<br/>orchestrator"]
        RULES["Business rules<br/>+ action engine"]
        REVIEW["Review policy"]
        RAG["RAG service"]
        EVALSVC["Evaluation runner"]
        AUD["Audit service"]
    end

    subgraph AI["AI layer (provider-agnostic)"]
        PROV["LLMProvider<br/>Anthropic · OpenAI · Demo"]
        STRUCT["Structured client<br/>validate + retry"]
        EMB["Embeddings<br/>OpenAI · local hashing"]
    end

    subgraph DATA["PostgreSQL + pgvector"]
        REL[("Customers · Policies<br/>Conversations · Messages")]
        AIDB[("AI analyses<br/>Reviews · Tasks · Audit")]
        VEC[("Knowledge chunks<br/>+ embeddings")]
    end

    Channels --> API
    FE <--> API
    API --> PIPE
    PIPE --> STRUCT --> PROV
    PIPE --> RULES --> REVIEW
    PIPE --> RAG --> EMB
    RAG --> VEC
    PIPE --> AUD
    API --> EVALSVC --> PIPE
    PIPE --> REL
    PIPE --> AIDB
```

Full detail, including trade-offs: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

---

## 5. AI pipeline

```mermaid
flowchart TD
    A["Inbound message"] --> B["Normalisation<br/>whitespace, control chars, length cap"]
    B --> C["Injection heuristics<br/>signal only, never a filter"]
    C --> D["Customer 360 context<br/>policies · history · open tasks"]
    D --> E["LLM classification + extraction<br/>prompt classification_v1"]

    E --> F{"Valid JSON?<br/>Valid schema?"}
    F -- no --> G["Retry with the concrete error<br/>(max LLM_MAX_RETRIES)"]
    G --> E
    F -- "still failing" --> H["Safe fallback<br/>UNKNOWN · confidence 0 · escalate"]
    F -- yes --> I["Deterministic business rules<br/>urgency can only go up"]

    H --> I
    I --> J{"Confident enough<br/>and no injection?"}
    J -- no --> K["Skip retrieval<br/>no fabricated grounding"]
    J -- yes --> L["RAG retrieval<br/>expand · embed · search · re-rank"]

    K --> M["Next-best-action engine"]
    L --> M
    M --> N["Response generation<br/>prompt response_v1, grounded"]
    N --> O["Citation verification<br/>drop sources that were not retrieved"]
    O --> P["Human review gate<br/>risk · urgency · confidence · grounding"]
    P --> Q["Persist analysis + task<br/>+ audit trail"]
    Q --> R{"Operator decision"}
    R -->|APPROVE| S["Record decision<br/>(simulated send)"]
    R -->|EDIT & APPROVE| S
    R -->|REJECT| T["Escalate to a human owner"]
```

Full detail, including failure handling: **[docs/AI_PIPELINE.md](docs/AI_PIPELINE.md)**.

---

## 6. Technology stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.12, Flask 3, SQLAlchemy 2 | Small, explicit, easy to read in review |
| Validation | Pydantic v2 | One schema drives the prompt, the DB and the API |
| Database | PostgreSQL 16 + pgvector | Relational business state *and* vectors in one store |
| Migrations | Alembic / Flask-Migrate | Autogenerated initial revision, reviewed and hand-patched for pgvector |
| Frontend | React 18, TypeScript, Vite, React Router | Standard, fast, no heavy UI dependency |
| Styling | Native CSS with design tokens | ~730 lines, no framework to explain |
| AI | Anthropic or OpenAI, behind an interface | Swappable; demo mode needs neither |
| Tests | pytest (222) · Vitest + Testing Library (29) | LLM mocked; everything else real |
| Infra | Docker Compose (db · backend · frontend) | One command, three services |

---

## 7. Repository structure

```
insurance-ai-copilot/
├── backend/
│   ├── app/
│   │   ├── __init__.py            # app factory (wiring only)
│   │   ├── cli.py                 # flask bootstrap / seed / ingest-knowledge / evaluate
│   │   ├── config.py              # env-driven settings, demo-mode resolution
│   │   ├── extensions.py
│   │   ├── models/                # enums · customer · conversation · ai · knowledge · evaluation
│   │   ├── schemas/               # ai_output.py (LLM contracts) · api.py (request validation)
│   │   ├── prompts/               # classification_v1.md · response_v1.md · rag_answer_v1.md
│   │   ├── routes/                # system · customers · conversations · analyses · knowledge · evaluations · audit
│   │   ├── services/
│   │   │   ├── ai/                # base · providers · demo_provider · demo_rules · embeddings · structured · factory
│   │   │   ├── rag/               # chunking · ingestion · vector_store · retriever
│   │   │   ├── workflows/         # context · business_rules · action_engine · review_policy · response_generation · pipeline
│   │   │   └── evaluation/        # metrics · runner
│   │   └── utils/                 # errors · request_context · text
│   ├── migrations/versions/       # Alembic initial schema
│   ├── scripts/seed_demo_data.py
│   ├── tests/                     # 222 tests
│   ├── Dockerfile · entrypoint.sh · requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/client.ts          # single typed HTTP client
│   │   ├── components/            # Layout · CopilotPanel · Customer360 · ConversationThread · ui
│   │   ├── pages/                 # Dashboard · Inbox · ConversationDetail · Customers · CustomerDetail · KnowledgeBase · Evaluations · AuditLogs
│   │   ├── hooks/useApi.ts
│   │   ├── types/api.ts           # mirrors the backend contracts
│   │   └── styles/index.css
│   └── Dockerfile · nginx.conf
├── data/
│   ├── knowledge_base/            # 10 synthetic procedure manuals (Spanish)
│   ├── synthetic_cases/           # 8 scripted demo conversations
│   └── evaluation/                # 60 labelled evaluation cases
├── docs/                          # ARCHITECTURE · AI_PIPELINE · EVALUATION · SECURITY_AND_LIMITATIONS · screenshots
├── docker-compose.yml · .env.example · README.md
```

---

## 8. Getting started

### Option A — Docker (recommended, one command)

```bash
cp .env.example .env          # optional; sensible defaults without it
docker compose up --build
```

The backend container waits for Postgres, applies migrations, seeds the demo
data and ingests the knowledge base automatically.

- Frontend → <http://localhost:5173>
- API health → <http://localhost:5001/api/health>

### Option B — Local, no infrastructure at all

The project deliberately runs with **no Docker, no PostgreSQL and no API key**:
it falls back to SQLite and demo mode. This is the fastest way to review it.

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export FLASK_APP=app:create_app
flask bootstrap                 # create schema + seed + ingest, in one step
flask run --port 5001
```

```bash
# Frontend (second terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173, proxies /api to :5001
```

### Verify

```bash
curl localhost:5001/api/health
# {"status":"ok","database":"ok","vector_backend":"portable-python","ai_demo_mode":true,...}
```

---

## 9. Environment variables

Everything is optional — see **[.env.example](.env.example)** for the annotated
list. The ones that matter:

| Variable | Default | Effect |
|---|---|---|
| `DATABASE_URL` | SQLite file | Set to a Postgres URL to use pgvector |
| `LLM_PROVIDER` | *(empty)* | `anthropic` \| `openai` \| empty → demo mode |
| `LLM_API_KEY` | *(empty)* | Missing key ⇒ demo mode, never a crash |
| `LLM_MODEL` | per provider | e.g. `claude-sonnet-4-20250514` |
| `AI_DEMO_MODE` | `false` | Force mock AI even with a key |
| `EMBEDDING_PROVIDER` | `hashing` | `openai` for real semantic embeddings |
| `EMBEDDING_DIMENSIONS` | `384` | **Fixed at migration time** — changing it needs a migration + re-ingest |
| `AI_CONFIDENCE_THRESHOLD` | `0.75` | Below this, a human always reviews |
| `RAG_TOP_K` | `5` | Chunks retrieved per query |
| `RAG_MIN_SIMILARITY` | `0.16` | Floor below which results are discarded |

---

## 10. Common tasks

```bash
cd backend && export FLASK_APP=app:create_app

flask bootstrap             # schema + seed + ingest (add --reset to wipe first)
flask db upgrade            # migrations only
flask seed                  # synthetic demo data only
flask ingest-knowledge      # (re)build the vector store; --force to re-embed
flask evaluate              # run the labelled suite and print metrics
```

### Running the tests

```bash
cd backend && .venv/bin/python -m pytest        # 222 tests
cd frontend && npm test                          # 29 tests
```

External LLM calls are mocked in the automated suite, so it runs offline and
deterministically. Point `LLM_API_KEY` at a real provider and run
`flask evaluate` for a live integration check.

### Running evaluation

From the UI: **Evaluations → Run evaluation**. From the CLI: `flask evaluate`.

Current **demo-mode baseline** (the deterministic mock, 60 cases):

| Metric | Result |
|---|---|
| Intent accuracy | 91.7% |
| Urgency accuracy | 85.0% |
| Insurance type accuracy | 93.3% |
| Action accuracy | 96.7% |
| Schema validation rate | 100% |
| Entity extraction F1 | 0.903 (P 0.82 / R 1.00) |
| **Human-review recall on risky cases** | **97.4%** |
| Human-review false-alarm rate | 47.6% |
| Avg latency | ~100 ms |

These are the numbers for the *keyword baseline*, not a language model. That is
the point: it is the floor a real LLM has to beat, and it is a genuinely useful
comparison. See **[docs/EVALUATION.md](docs/EVALUATION.md)**.

---

## 11. Using a real LLM

```bash
# .env
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-...
LLM_MODEL=claude-sonnet-4-20250514
```

Restart the backend. The banner switches from **Demo AI Mode** to **Live AI**,
`ai_analyses.demo_mode` becomes `false`, and the same evaluation suite now
measures the model. For real semantic retrieval, additionally set
`EMBEDDING_PROVIDER=openai`, `EMBEDDING_API_KEY=...` and `EMBEDDING_DIMENSIONS=1536`,
then re-run migrations and `flask ingest-knowledge --force`.

---

## 12. Demo walkthrough

A suggested path through the seeded demo data:

1. **Dashboard** — queue health, review backlog, AI latency.
2. **Inbox** — one queue across three channels, filterable by AI label.
3. **`DEMO-01` motor claim** — structured extraction, RAG sources, next action,
   then edit and approve.
4. **`DEMO-06` injury claim** — the rule engine overrides urgency to `CRITICAL`
   and forces escalation.
5. **`DEMO-05` ambiguous** — low confidence, retrieval skipped, asks for
   clarification instead of guessing.
6. **`DEMO-08` prompt injection** — flagged, no retrieval, routed to compliance,
   no data leaked.
7. **RAG Playground** — retrieval with similarity scores, including a nonsense
   query that correctly returns nothing.
8. **Evaluations** — metrics and the per-case failure table.
9. **Audit logs** — the same decisions, recorded.

The eight scripted cases are in
[`data/synthetic_cases/demo_cases.json`](data/synthetic_cases/demo_cases.json).

---

## 13. Design decisions

| Decision | Reasoning |
|---|---|
| **Structured output, not free text** | The analytical stage feeds routing and the database. Parsing prose would make every downstream component fragile. |
| **Deterministic rules after the LLM** | Urgency and escalation are business policy. They must be stable, testable and signed off by a human — not re-derived probabilistically each run. |
| **Rules only raise urgency** | An unnecessary escalation costs an operator five minutes; a missed injury costs far more. |
| **Relational storage** | The core objects (customer, policy, conversation, task) are relational, with real integrity constraints. Vectors are one column, not the architecture. |
| **RAG for procedural facts** | Policy procedures change and are company-specific. Retrieval keeps them editable in Markdown and makes answers citable. |
| **Retrieval skipped on low confidence** | Retrieving for an unclear message produces confident-looking citations for an untrustworthy answer. Refusing is safer. |
| **Citations verified server-side** | A model can claim grounding it does not have. Sources not actually retrieved are stripped before storage. |
| **Human approval on all high-risk intents** | Claims, complaints, cancellations and payments have legal consequence. Auto-approval eligibility exists but is deliberately narrow. |
| **Demo mode as a first-class path** | A reviewer can run everything in 60 seconds without a key — and is never misled about what produced the output. |
| **Prompts as versioned files** | `prompt_version` in the database means "which prompt produced this?" is answerable months later. |
| **Two vector backends** | pgvector in Docker; a portable Python implementation for zero-setup review. One interface, chosen by dialect. |

---

## 14. Reliability and AI safeguards

1. **Schema validation** on every model output; invalid enums rejected.
2. **Informed retries** — the validation error is fed back into the retry.
3. **Safe fallback** — persistent failure yields `UNKNOWN`, confidence 0 and a
   forced escalation, never a silent wrong answer.
4. **Confidence thresholds** — a routing floor (0.45) and a review threshold (0.75).
5. **Grounding** — procedural claims must come from retrieved chunks; citations
   are verified against what was actually retrieved.
6. **Explicit refusal** — with no usable sources the system says it lacks
   information rather than inventing an answer.
7. **Prompt-injection handling** — customer text is always delimited and treated
   as data; suspicious text is flagged, retrieval is skipped, the case goes to
   compliance, and no cross-customer data is ever in scope.
8. **Human-in-the-loop** on every high-risk path.
9. **Audit trail** with request-ID correlation, excluding message bodies.
10. **No automatic external actions** — sending is simulated.

---

## 15. Known limitations

- **Demo-mode AI is a keyword matcher**, not a model. Labelled as such everywhere.
- **Local hashing embeddings are lexical, not semantic** — "coche" will not
  retrieve "vehículo" unless both appear. Real embeddings need an API key.
- **No authentication or authorisation.** Every caller is `demo.operator`.
- **Evaluation runs without customer context**, which isolates message
  understanding but means context-dependent urgency (e.g. "expires in 4 days"
  stated in text) is not scored. One known miss, documented in EVALUATION.md.
- **Inbox filtering by AI label happens in Python**, not SQL — fine at POC
  volume, not at 100k conversations.
- **Single-tenant, no rate limiting, no background job queue** — analysis is
  synchronous inside the request.
- **Running the full evaluation from the UI blocks the request.** With the demo
  engine the 60 cases finish in ~6 s. With a real LLM each case makes two API
  calls, so a full run takes minutes and will exceed the nginx proxy timeout
  (180 s). Use `flask evaluate` from the CLI, or `POST /api/evaluations/run`
  with a `limit`, until the runner moves to a job queue.
- **The knowledge base is invented.** It is realistic, not legally accurate.

Full list: **[docs/SECURITY_AND_LIMITATIONS.md](docs/SECURITY_AND_LIMITATIONS.md)**.

---

## 16. What production would need

1. **AuthN/AuthZ** — SSO, per-team RBAC, real reviewer identity in the audit trail.
2. **Async processing** — Celery/RQ for analysis, with retries and dead-letter handling.
3. **Real channel integrations** — WhatsApp Business API, IMAP/Graph, telephony STT.
4. **Retrieval upgrade** — hybrid BM25 + vector, HNSW index, reranking, chunk-level evaluation.
5. **Production observability** — OpenTelemetry traces spanning HTTP → pipeline → provider, cost per case, drift alerts on confidence and approval rate.
6. **Evaluation on annotated production data**, plus regression gates in CI on
   review recall.
7. **Data governance** — retention policy, right-to-erasure, DPA with the model
   provider, PII redaction before any external call.
8. **Resilience** — provider failover, circuit breaker, response caching, budget caps.

---

## 17. Screens

| Screen | What it demonstrates |
|---|---|
| **Dashboard** | Queue health, review backlog, intent/urgency mix, AI latency and approval rate |
| **Unified Inbox** | Three channels in one queue, filterable by channel, intent, urgency, status and review state |
| **Conversation detail** | Thread · Customer 360 · AI Copilot, with sources, rule overrides, the three review actions and collapsible technical metadata |
| **Customers** | Searchable book; per-customer policies, conversations, tasks and AI case history |
| **Knowledge Base** | Ingested documents, chunk boundaries, and a **RAG Playground** showing retrieval with similarity scores |
| **Evaluations** | Run the labelled suite; accuracy, safety recall, latency, and a per-case failure table |
| **Audit Logs** | Append-only trail of every AI decision and human sign-off, filterable by action |

**Prompt injection (`DEMO-08`).** The message is treated as data: retrieval is
skipped, confidence drops and the case is routed to compliance for a human.

![Prompt injection flagged by the deterministic rules](docs/screenshots/prompt-injection.png)

**RAG Playground.** Retrieved chunks with their similarity scores. The banner
states the limit of the local embeddings: they are lexical, not semantic.

![RAG Playground with similarity scores](docs/screenshots/rag-playground.png)

**Evaluations.** Metrics on the 60 labelled cases and the per-case table, here
filtered to the failures, including missed reviews and false alarms.

![Evaluation run on the labelled dataset](docs/screenshots/evaluations.png)
