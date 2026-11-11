# Security, Privacy and Limitations

**This is a proof of concept. It is not production software, and this document
exists so that nobody mistakes it for one.**

No claim of GDPR compliance is made anywhere in this repository. The system
processes only invented data and has never handled a real customer record.

---

## 1. Data in this repository

Everything is synthetic:

| Data | Origin |
|---|---|
| 20 customers | Invented names, `@example.invalid` addresses, generated phone numbers |
| 39 policies | Generated numbers, dates chosen to exercise the business rules |
| 42 conversations, 102 messages | Written for this project |
| 10 procedure manuals | Written for this project; realistic in shape, not legally accurate |
| 60 evaluation cases | Written for this project |

`example.invalid` is reserved by RFC 2606 and can never route mail. No real
person, policy, vehicle, claim or company is represented, and no proprietary
material from any organisation was used.

The procedure documents reference Spanish insurance concepts (the seven-day
claim notice period, the one-month opposition to renewal, suspension of cover
one month after an unpaid premium). These are plausible and used consistently,
but they are **illustrative, not legal advice**, and a real deployment would
replace all ten documents with the brokerage's own reviewed procedures.

---

## 2. What *is* implemented

### Input handling
- Pydantic validation on every request body; unknown fields rejected (`extra="forbid"`).
- Enum validation on query parameters — an invalid filter returns 422, not a 500.
- Message length capped at 8 000 characters before any API call.
- Control characters stripped during normalisation.
- SQLAlchemy parameterised queries throughout; the one raw SQL statement (the
  pgvector search) uses bound parameters.
- An inbound `X-Request-ID` is attacker-controlled, so it is validated against
  a strict alphabet and length before being stored, logged or echoed back;
  anything else is replaced with a generated id.

### AI-specific controls
- **Schema validation** on every model output. An invalid enum cannot reach the
  database.
- **Bounded retries** with the concrete error fed back, then a safe fallback.
- **Prompt-injection heuristics** — 13 patterns, English and Spanish,
  accent-insensitive. A match skips retrieval, forces escalation to compliance
  and writes an audit entry.
- **Structural injection defence** — customer text is always delimited and
  labelled untrusted, and **no code path can read another customer's data**: the
  context builder receives one customer object.
- **Grounding** — procedural facts must come from retrieved chunks, and
  citations are verified server-side against what was actually retrieved.
- **Explicit refusal** when retrieval returns nothing.
- **Human-in-the-loop** on every high-risk intent, low-confidence case and
  ungrounded draft.
- **No automatic external actions.** Sending is simulated; the audit trail
  records `delivery: SIMULATED_ONLY`.

### Privacy-shaped engineering
- Secrets come from the environment; `.env` is gitignored, `.env.example`
  contains no real values.
- **Audit metadata never contains message bodies or draft responses** —
  `_sanitise()` strips them by key.
- Message bodies are not logged; `LOG_MESSAGE_BODIES` defaults to `false`.
- A `redact()` helper masks emails, phones, IBANs and plates for the rare log
  line that needs an excerpt.
- Database credentials are stripped from the startup log line.
- Errors return a generic message; SQL and stack traces never reach the client.
- Containers run as a non-root user.
- The prompt forbids requesting card numbers or banking credentials, mirroring
  the internal procedure document.

---

## 3. What is **NOT** implemented

This section is the important one.

### Authentication and authorisation — absent entirely
- **No login.** Every API endpoint is open to anyone who can reach the port.
- **No authorisation.** No roles, no per-team scoping, no ownership checks.
- The reviewer identity is a client-supplied string (`demo.operator`). It is
  recorded in the audit trail and is **completely unverified** — the audit trail
  is therefore not tamper-evident and would not stand up as evidence.
- No session management, CSRF protection, or rate limiting.

### Data protection — not production-grade
- **No encryption at rest.** Postgres uses default settings; no column-level
  encryption on customer data.
- **No TLS.** HTTP everywhere; the compose stack terminates nothing.
- **No data retention or deletion policy.** Nothing expires. Right-to-erasure is
  unimplemented — deleting a customer would cascade, but there is no process,
  no verification, and no audit of the deletion itself.
- **No DPA considerations for the model provider.** In real deployment, customer
  message content would be sent to a third party; that requires a data processing
  agreement, a documented lawful basis, transfer safeguards, and a decision about
  zero-retention endpoints. None of that is addressed here.
- **No PII redaction before external calls.** Full message text and customer
  context go to the provider as-is.
- **No pseudonymisation or anonymisation.**

### Secrets management
- Environment variables and a `.env` file. No vault, no rotation, no per-service
  scoping, no leak detection.

### Operational maturity
- **No production observability** — no OpenTelemetry, no metrics backend, no
  alerting, no dashboards. Logging is stdout only.
- **No backups, no disaster recovery, no tested restore.**
- **No CI/CD pipeline**, no automated dependency or container scanning.
- **No penetration testing, no threat model, no security review.**
- **No rate limiting or quota control** on the AI endpoints — an open,
  unauthenticated endpoint that spends money per call is a real abuse vector.
- **No file upload**, therefore no malware scanning — but note that a real
  claims workflow *requires* uploads, and that is a significant security surface
  this POC does not touch.
- **No multi-tenancy.** Single brokerage, single database, no isolation.
- **No high availability.** Single instance of everything; analysis runs
  synchronously inside the request.

### AI-specific gaps
- **Injection heuristics are not a security boundary.** They are regexes and can
  be bypassed by paraphrasing. The real protection is the data model, not the
  patterns.
- **No output moderation** beyond the grounding checks.
- **No provider failover, circuit breaker or budget cap.**
- **The demo-mode rule engine is not AI** and is labelled as such everywhere it
  appears — in the API (`demo_mode: true`), on every stored analysis, and as a
  persistent banner in the UI.
- **Local hashing embeddings are lexical, not semantic.** They demonstrate the
  pipeline; they do not demonstrate semantic retrieval.
- **Retrieval quality is unmeasured.** No recall@k, no labelled relevance set.

---

## 4. Threat notes

| Concern | Current state |
|---|---|
| **Prompt injection → data exfiltration** | Structurally mitigated: no code path reads another customer's data, and the model has no tools. Heuristics add detection and escalation on top. Tested. |
| **Prompt injection → harmful draft** | Mitigated by human review; a flagged message never produces an auto-approvable draft. |
| **Hallucinated policy facts** | Mitigated by grounding, server-side citation verification, explicit refusal, and a prompt that forbids stating unverified coverage terms. Not eliminated — a model can still paraphrase a retrieved chunk incorrectly, which is why a human approves. |
| **Unauthorised access** | **Not mitigated.** No auth exists. |
| **Cost abuse** | **Not mitigated.** No rate limiting or budget cap. |
| **Audit tampering** | **Not mitigated.** Reviewer identity is unverified; logs are ordinary rows. |
| **Data at rest exposure** | **Not mitigated.** No encryption. |

---

## 5. Minimum work before any real data

Ordered by dependency, not by preference:

1. **Authentication and authorisation** — SSO, per-team RBAC, server-derived
   reviewer identity. Nothing else matters until this exists.
2. **TLS everywhere**, encryption at rest, secrets in a managed vault.
3. **Legal groundwork** — DPA with the model provider, lawful basis, records of
   processing, retention schedule, right-to-erasure process, DPIA.
4. **PII minimisation before external calls** — redact what the model does not
   need.
5. **Rate limiting and budget caps** on AI endpoints.
6. **Tamper-evident audit** — append-only storage, verified identity.
7. **Production observability** — traces, metrics, alerts on AI failure and
   approval-rate drift.
8. **Security review** — threat model, dependency and container scanning,
   penetration test.
9. **Backups with a tested restore.**
10. **Evaluation on real annotated data**, with CI gates on the safety metric.

---

## 6. Honest summary

This project demonstrates that I can design and build an AI-enabled business
workflow with structured outputs, deterministic guardrails, retrieval grounding,
human oversight, evaluation and auditability.

It does **not** demonstrate a production-ready, secure, compliant system, and it
does not claim to. The gap between the two is exactly what §3 and §5 enumerate —
and being able to name that gap precisely is, I would argue, part of the point.
