# Evaluation

An AI feature without evaluation is a demo, not a product. This document
describes the dataset, what each metric means, what the current numbers are, and
— importantly — what this evaluation **cannot** tell you.

---

## 1. What is evaluated

**The whole decision system, not the model call.**

Each case runs through the same `AnalysisPipeline` the product uses:
classification → schema validation → deterministic business rules → retrieval
gate → next-best-action → review gate. Scoring the raw LLM output would measure
the wrong thing, because what ships is the pipeline.

That is why `urgency_accuracy` is measured *after* the rule engine, and why
`action_accuracy` scores the action engine's output rather than the model's
suggestion.

---

## 2. Dataset construction

`data/evaluation/evaluation_cases.json` — **60 labelled cases**, all synthetic.

### Coverage

| Dimension | Coverage |
|---|---|
| Intents | All 12, minimum 3 cases each |
| Insurance types | MOTOR, HOME, HEALTH, LIFE, TRAVEL, BUSINESS, UNKNOWN |
| Channels | WhatsApp (short, informal), Email (long, formal), Phone transcripts |
| Difficulty | `STANDARD` · `AMBIGUOUS` · `HIGH_RISK` · `NOISY` · `ADVERSARIAL` |

### Deliberately hard cases

The dataset is not a happy path. It includes:

- **Ambiguous** — *"No me funciona lo del seguro"*. Correct behaviour is low
  confidence and a clarification request. Confident classification here is a
  **defect**, and the dataset scores it as one.
- **Noisy** — WhatsApp shorthand, missing accents, emoji, run-on sentences.
- **Boundary** — EV-031 asks which documents a water-damage claim needs *without
  reporting a claim*. `DOCUMENT_REQUEST` or `CLAIM` are both arguable; the case
  exists precisely to see which way a system leans.
- **Conflicting signals** — EV-047 mentions double billing but the dominant
  intent is a complaint with legal escalation. The internal escalation procedure
  says complaints win; the label follows the procedure.
- **Adversarial** — three prompt-injection cases, including one that mixes a
  legitimate question with an injection.
- **Known over-escalation trap** — EV-010 is a health *reimbursement* request
  that mentions a knee injury. A keyword system reads "lesión" and escalates to
  `CRITICAL`. The label is `MEDIUM`, so the cost of the conservative injury rule
  is measured rather than hidden.

### Labelling method

Labels are the outcome a competent operator would choose, following the
brokerage's own written procedures in `data/knowledge_base/`. Where a case is
genuinely ambiguous, the `notes` field records why the label was chosen.

Expected entities are **partial by design**: only the entities that matter for
routing are labelled. A predicted entity the dataset does not label is not
counted as a false positive.

---

## 3. Metrics

| Metric | Definition | Reads as |
|---|---|---|
| `intent_accuracy` | Exact match over 12 labels | Does it understand what the customer wants? |
| `urgency_accuracy` | Exact match, **after** business rules | Does the case get the right priority? |
| `insurance_type_accuracy` | Exact match over 8 labels | Does it identify the product? |
| `action_accuracy` | Exact match on the action engine's decision | Does the right thing happen next? |
| `schema_validation_rate` | Share of cases that validated without fallback | Structural reliability of the AI layer |
| `entity_extraction.{precision,recall,f1}` | Over labelled entity keys | Are the facts right? |
| **`human_review_recall_on_risky`** | Of cases that **must** reach a human, how many were flagged | **The safety metric** |
| `human_review_false_alarm_rate` | Of safe cases, how many were flagged unnecessarily | The cost of caution |
| `avg_latency_ms`, `p95_latency_ms` | Per case, end to end | Operational feasibility |
| `total_input_tokens`, `total_output_tokens` | Summed usage | Cost basis (zero in demo mode) |
| `intent_confusion` | Actual → predicted counts | *Where* it goes wrong, not just how often |

### Why review recall is the metric that matters

Accuracy metrics measure usefulness. **Review recall measures safety.**

A missed risky case means a draft about a claim, a cancellation or a payment
could reach a customer without a human reading it. Every other metric can
degrade gracefully; this one cannot. It is the number I would put a CI gate on.

Its counterpart, `human_review_false_alarm_rate`, is reported alongside because
a system that flags everything scores a perfect 100% recall and is useless. The
pair has to be read together.

The current false-alarm rate is **47.6%**: roughly half the cases that could
safely have been auto-approved are still routed to a human. That is a real cost
— it is operator time — and it is the direct consequence of the conservative
choices in §4 (high-risk intents always reviewed, ungrounded drafts always
reviewed). Whether 47.6% is acceptable is a business decision, not a technical
one; the point of measuring it is that the business gets to make that decision
with a number in front of them rather than a feeling.

### Entity matching

Lenient string comparison, because *"1234ABC"* and *"1234 abc"* are the same
plate: case-folded, whitespace-stripped, with substring matching for values
longer than three characters (so `"ayer"` matches `"ayer por la tarde"`).

---

## 4. Current baseline — demo mode

The mock rule engine, 60 cases:

| Metric | Result |
|---|---|
| Intent accuracy | **91.7%** |
| Urgency accuracy | 85.0% |
| Insurance type accuracy | 93.3% |
| Action accuracy | **96.7%** |
| Schema validation rate | 100% |
| Entity F1 | 0.903 (P 0.824 / R 1.000) |
| **Human-review recall on risky** | **97.4%** |
| Human-review false-alarm rate | 47.6% |
| Avg latency | ~100 ms |

**Read these correctly.** This is a Spanish keyword matcher, not a language
model. It is a *baseline* — the floor a real LLM has to beat. Publishing it is
deliberate: if an expensive model cannot beat a regex on this taxonomy, that is
worth knowing before shipping it.

Schema validation is trivially 100% in demo mode, since the mock emits valid JSON
by construction. That number only becomes meaningful with a real provider.

### Known failures, and why they are left in

**The one missed risky case (EV-015).** A customer says their motor policy
expires *in four days*. A human annotator reads that and marks it `HIGH`. The
system does not: renewal urgency is driven by the **expiry date in the database**,
and evaluation deliberately runs without customer context. Given real context,
`renewal_imminent` fires correctly — which is covered by a unit test.

This is a genuine, structural limitation of the evaluation setup, not a bug.
Reporting 97.4% with a named cause is more useful than tuning it to 100%.

**Over-escalation (EV-010).** The health reimbursement mentioning a knee injury
is escalated to `CRITICAL` by the conservative injury rule. Expected: `MEDIUM`.
This is the asymmetry from ARCHITECTURE.md §5 doing exactly what it is supposed
to, and this case is how its cost gets measured.

**Adversarial intent labels (EV-058/059/060).** The prompt tells a real model to
classify injections as `GENERAL_SUPPORT`; the keyword baseline has no rule for
English injection text and returns `UNKNOWN`. The *safety* behaviour is still
correct — all three escalate to compliance — so `action_accuracy` is unaffected
while `intent_accuracy` takes the hit. Correct labels for the product, honest
failure for the baseline.

---

## 5. Running it

```bash
# CLI
cd backend && FLASK_APP=app:create_app flask evaluate --label "before prompt change"

# API
curl -X POST localhost:5001/api/evaluations/run \
     -H 'Content-Type: application/json' -d '{"label":"api run"}'

# UI
Evaluations → Run evaluation
```

Runs are **persisted** (`evaluation_runs` + `evaluation_results`) so prompt
changes can be compared over time. That is the workflow: change
`classification_v1` → `classification_v2`, re-run, compare the two rows in the
run-history table.

The per-case table defaults to **failures only**, because that is where the
information is.

---

## 6. Limitations of synthetic evaluation

Stated plainly, because these matter more than the numbers:

1. **I wrote both the cases and the system.** Even with care, the dataset
   inherits my assumptions about how customers write. Real messages will be
   worse — longer, more contradictory, mixing three requests in one paragraph.
2. **60 cases is small.** Per-intent accuracy rests on 3–12 examples, so
   individual figures have wide confidence intervals. The aggregate is
   indicative, not precise.
3. **Single annotator, no inter-annotator agreement.** For genuinely ambiguous
   cases (EV-031, EV-049), a second annotator would likely disagree, and there
   is no way to quantify that here.
4. **No customer context**, as discussed above.
5. **Response quality is not scored.** The pipeline is scored on classification,
   routing and safety. Whether the Spanish draft is *good* — tone, completeness,
   whether it would actually satisfy a customer — is not measured at all. That
   needs human rating or an LLM-as-judge rubric.
6. **Retrieval quality is not scored directly.** There is no labelled
   query→relevant-chunk set, so recall@k and MRR are not computed. Only the
   downstream effect (grounded vs not) is visible.
7. **No adversarial breadth.** Three injection cases is a smoke test, not a red
   team.
8. **Cost and latency are not representative** in demo mode: no network, no
   tokens.
9. **The runner is synchronous.** Triggering a full 60-case run from the UI
   holds the HTTP request open for its whole duration. That is fine at ~6 s in
   demo mode but not with a real model, where a run takes minutes and will hit
   the proxy timeout. Use the CLI (`flask evaluate`) or pass a `limit` until
   the runner is moved onto a job queue.

---

## 7. How this would evolve with production data

1. **Replace synthetic cases with sampled real ones.** Stratify by intent and
   channel, target 500–1000 cases, and re-label with two annotators plus an
   adjudicator. Track Cohen's κ.
2. **Mine labels from operator behaviour.** Every `EDIT_AND_APPROVE` is a free
   label: the diff between the AI draft and the sent text says exactly what was
   wrong. Every `REJECT` with notes is a labelled failure. This is the highest
   value dataset in the system and it accumulates automatically — the schema
   already stores both versions.
3. **Add retrieval evaluation.** Label relevant chunks per query; measure
   recall@k, MRR and nDCG. Retrieval failures currently masquerade as generation
   failures.
4. **Add response-quality scoring.** A rubric (accuracy, completeness, tone,
   no-invention) rated by humans on a sample, plus an LLM judge validated against
   those ratings before being trusted at scale.
5. **CI gates.** Block a prompt or model change that drops
   `human_review_recall_on_risky` below an agreed floor, or that moves intent
   accuracy by more than a set delta.
6. **Production monitoring as continuous evaluation.** Confidence distribution
   drift, approval-rate drift by intent, edit-rate by intent, escalation-rate
   drift. A model that silently degrades shows up here long before anyone files
   a complaint.
7. **Slice metrics.** Overall accuracy hides the case that matters. Report by
   intent, by channel, and by message length — a system that is 95% accurate
   overall and 60% on cancellations has a specific, fixable problem.
