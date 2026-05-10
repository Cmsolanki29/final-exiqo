# Model Card — `multi_model_orchestrator` v1 (Phase 12)

> **Status:** SHIPPED, default OFF.
> Master switch: `PHASE_12_ORCHESTRATOR_ENABLED` (boolean).
> When OFF, `/api/risk/orchestrator/decide` becomes a transparent
> passthrough — the baseline `HybridScorer + DecisionEngine` action is
> returned unchanged and only the tier label is recorded for analytics.

## 1. What it is

A single decision-maker that **wraps** the existing scoring and
decision pipeline.  It does not replace any model.  Its job is to:

1. Label which tier (combination of models) actually contributed to
   the decision — for analytics and the UI.
2. Selectively *escalate* high-stakes or model-disagreement cases by
   invoking:
   - **Phase 9** — the LLM Investigation Agent (fully autonomous,
     uses tools to investigate the user/merchant).
   - **LLM-as-Judge** — a separate, single-shot LLM call that
     cross-checks the baseline action and may escalate it.
3. Persist the full decision lineage to `orchestration_decisions`.

This pattern mirrors PhonePe's published 2024-2025 architecture and
the "judge / verifier" patterns published by Anthropic and FIS.

## 2. Tier ladder (deterministic, pure logic)

| Tier | Range / Trigger | Cost | Latency target |
| --- | --- | --- | --- |
| `tier_0_rules`    | score < `PHASE_12_TIER0_MAX` (default 30) | $0 | <20 ms |
| `tier_1_xgb`      | score < `PHASE_12_TIER1_MAX` (default 60) | $0 | <100 ms |
| `tier_2_gnn`      | score < `PHASE_12_TIER2_MAX` (default 75) **and** GNN signal present | $0 | <130 ms |
| `tier_3_dnn`      | score < `PHASE_12_TIER3_MAX` (default 85) **and** DNN shadow score present | $0 | <150 ms |
| `tier_4_llm_agent`| score ≥ `PHASE_12_TIER3_MAX` | ~$0.001-0.003 (Groq) | ~2-5 s if synchronous |
| `tier_5_judge`    | *Modifier* — applied on top of any tier when the policy says judge is needed | ~$0.0005 (Groq) | +200-700 ms |

The orchestrator never picks a tier "above" what the available signals
support: if Phase 10's GNN feature flag is off (no `gnn_emb_dim` in
signals) a 65-score decision lands in **tier_1_xgb**, not tier_2_gnn.
This is intentional — the tier label has to reflect what was actually
spent, not a paper menu.

## 3. Judge invocation rules

The LLM-as-Judge runs only when the orchestrator is enabled, judge is
enabled, and one of:

1. Tier ∈ {tier_3_dnn, tier_4_llm_agent} — high-stakes by default.
2. The baseline rule engine fired an override **and** the score is
   below `PHASE_12_TIER1_MAX` (rules and ML say different things).
3. `|dnn_shadow_score - baseline_score| ≥ PHASE_12_DNN_DISAGREE_DELTA`
   (default 25 points) — model disagreement.

The judge is **single-shot, no tool use**.  It receives the
PII-redacted transaction, the baseline decision, the per-model
signals, and the optional Phase 9 investigation narrative.  It returns
a structured JSON opinion.

## 4. The judge can only escalate

A judge that wants to **relax** the action (e.g. propose `allow` for a
baseline `block`) is **logged but ignored**.  The orchestrator's action
ladder is `allow < review < challenge < block`; any judge suggestion
below the baseline rank is treated as commentary only.

This is a deliberate safety property: an LLM hallucinating "looks fine"
on a real fraud must never override the rule engine.

## 5. Confidence gate

Even when the judge wants to escalate, the override is only applied
when `judge.confidence ≥ PHASE_12_JUDGE_MIN_CONFIDENCE` (default 0.70).
A timid judge (confidence < 0.70) is recorded in the audit trail but
does not change the action.

## 6. Cost & budget

The judge shares the **Phase 9 daily budget guard** (single
`risk_llm_budget_log` table, single daily cap).  When the cap is
exceeded the judge returns `error="budget_exceeded"` and the
orchestrator silently keeps the baseline action — fail-closed.

Realistic cost per judge call (Llama 3.3 70B on Groq):
* Input: ~600-1500 tokens (system prompt + JSON of decision context).
* Output: ~150-400 tokens (judgment JSON).
* Cost: ~$0.0005 per call.

Realistic cost per *full* tier-4 decision (judge + investigation):
~$0.0015-0.0035.

## 7. Honest caveats

* **No live observations of judge accuracy yet.**  We do not have a
  labelled dataset of borderline decisions to measure how often the
  judge improves vs. degrades the baseline.  Promotion of judge
  overrides into the production scoring path requires a 7-day
  shadow-mode comparison study (queued as Phase 12.1).
* **Latency floor:** every LLM call is single-digit-second territory
  on a slow day.  The orchestrator uses synchronous investigation only
  when `PHASE_12_SYNC_INVESTIGATION=true` (default off) for exactly
  this reason — high-risk transactions get the async fire-and-forget
  path from `alert_consumer.py`, not the sync path.
* **Single-region budget guard.** If we ever multi-process, the
  current SELECT-then-UPSERT can race; the documented fix is to swap
  to a single atomic UPSERT statement (see `budget_guard.py`).

## 8. Rollback

* **Soft (instant):** set `PHASE_12_ORCHESTRATOR_ENABLED=false`. The
  endpoint becomes a passthrough; existing rows in
  `orchestration_decisions` remain queryable.
* **Hard:** `git revert` the Phase 12 commit. The
  `orchestration_decisions` table is append-only and PII-free, so
  leaving it in place is safe.

## 9. What would change this card

The card moves from "shipped, conservative defaults" to "judge
enabled by default" when:

1. A 7-day shadow study shows judge overrides reduce false positives
   without raising false negatives on every user segment.
2. The Phase 8 feedback flywheel produces ≥ 1 000 real `is_fraud`
   labels so we can measure judge precision and recall directly.
3. p99 judge latency stays under 1 s in production traffic patterns.
