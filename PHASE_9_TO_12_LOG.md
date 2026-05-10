# Phase 9-12 — 2025/2026 Fintech Parity Upgrade

> Branch: `feature/phase-9-to-12-2026-parity`
> Goal: Bring SmartSpend / EXIQO from a 2022-era ML stack to architectural
> parity with PhonePe, IBM Safer Payments, FIS+Anthropic, and NVIDIA Blueprint.

This log is updated **per milestone**, not per commit.  Each phase is
strictly feature-flagged: setting the relevant `PHASE_x_*_ENABLED` to
`false` in `.env` cleanly disables the new code paths.

---

## Phase 9 — LLM Investigation Agent (Agentic AI)

**Status:** ✅ Implemented (this milestone)
**Closes gap to:** IBM Safer Payments, FIS+Anthropic, CommBank, PhonePe.

### What it does
When a transaction is scored at `risk_score >= PHASE_9_AUTO_TRIGGER_SCORE`
(default 60) — or an admin clicks "Run Investigation" — an LLM agent
investigates using a six-tool toolbox and returns:

* a structured decision (`fraud_confirmed` / `legitimate` / `inconclusive`),
* a 2-3 sentence plain-English narrative (Hinglish allowed),
* `key_evidence` bullets,
* optional `suggested_rules` for the rules engine,
* full token / cost / latency telemetry.

Each investigation is persisted to `risk_investigations` with PII redacted
and the day's spend logged in `risk_llm_budget_log`.

### Provider — Groq (OpenAI-compatible)
| Setting | Value |
| --- | --- |
| SDK | `openai>=1.51` (already pinned) pointed at `https://api.groq.com/openai/v1` |
| API key | `GROQ_API_KEY` (already in `.env`) |
| Default model | `llama-3.3-70b-versatile` |
| High-stakes (score ≥ 85) | `llama-3.3-70b-versatile`, `temperature=0.1` |
| Fallback | `llama-3.1-70b-versatile` (auto-retry on `model_not_found`) |
| Tool calling | OpenAI-compatible function-calling format |
| Pricing | $0.59 / 1M input, $0.79 / 1M output |
| Realistic cost / investigation | $0.001 – $0.003 |
| Default daily cap | $1.00 (`PHASE_9_DAILY_BUDGET_USD`) |

### Files added
```
backend/database/migrations/009_phase9_investigations.sql
backend/services/risk_common/__init__.py
backend/services/risk_common/pii_redactor.py
backend/services/risk_common/budget_guard.py
backend/services/risk_common/groq_llm_client.py
backend/services/phase_9_agent/__init__.py
backend/services/phase_9_agent/agent.py
backend/services/phase_9_agent/investigation_service.py
backend/services/phase_9_agent/prompts/system_prompt.txt
backend/services/phase_9_agent/prompts/investigation_template.txt
backend/services/phase_9_agent/tools/__init__.py
backend/services/phase_9_agent/tools/base_tool.py
backend/services/phase_9_agent/tools/user_history_tool.py
backend/services/phase_9_agent/tools/merchant_lookup_tool.py
backend/services/phase_9_agent/tools/fraud_pattern_tool.py
backend/services/phase_9_agent/tools/geo_velocity_tool.py
backend/services/phase_9_agent/tools/blacklist_tool.py
backend/services/phase_9_agent/tools/shap_context_tool.py
backend/routes/investigations.py
backend/tests/test_phase9_agent.py
```

### Files modified (additive only)
```
backend/core/config.py            — Phase 9 settings block
backend/main.py                   — import + register investigations router
backend/workers/alert_consumer.py — auto-trigger on score >= threshold
backend/requirements.txt          — added groq, torch, networkx pins
```

### Database
* Migration `009_phase9_investigations.sql` applied — creates
  `risk_investigations` and `risk_llm_budget_log`.

### API surface (new)
| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET`  | `/api/risk/investigations/health` | open | feature-flag + LLM availability |
| `POST` | `/api/risk/investigations/{txn_id}/run` | `X-Admin-Token` | manual trigger |
| `GET`  | `/api/risk/investigations/{txn_id}` | `X-Admin-Token` | latest investigation row |
| `GET`  | `/api/risk/investigations/budget/today` | `X-Admin-Token` | today's spend rollup |

### Hard safety rules in code
1. **PII redaction** — every transaction, every tool output passes through
   `services.risk_common.pii_redactor.redact_dict` before being sent to Groq.
2. **Budget guard** — `BudgetGuard.check_and_reserve` runs before every LLM
   call.  Over-cap → `BudgetExceeded` → agent returns `inconclusive`.
3. **Confidence floor** — even if the model says `fraud_confirmed`, a
   confidence < 0.6 is forced to `inconclusive` for human review.
4. **Round cap** — max 8 tool-call rounds per investigation.
5. **Wall-clock timeout** — 30 s, after which the agent returns `inconclusive`.
6. **Fail-safe** — every error path persists an `inconclusive` row with
   `error` populated.  Investigations never raise out to callers.
7. **Feature flag** — `PHASE_9_AGENT_ENABLED=false` (default) makes the
   whole subsystem a no-op: no DB writes, no LLM calls, no cost.

### Tests
`backend/tests/test_phase9_agent.py` — runs without network.  Coverage:

* PII redactor: 6-pattern coverage + recursive dict.
* Budget guard: over-cap raises, under-cap allows, pricing math.
* `FraudPatternTool`: KYC-scam matches, benign transactions don't.
* `BlacklistTool`: static-layer hit when DB unavailable.
* Agent: disabled flag → inconclusive; missing API key → inconclusive;
  end-to-end with mocked Groq tool-call → final JSON; low-confidence →
  forced inconclusive.

### Configuration — new env vars
```dotenv
# Phase 9 — opt-in
PHASE_9_AGENT_ENABLED=false             # set to true to turn the agent on
PHASE_9_DAILY_BUDGET_USD=1.00           # daily LLM spend cap, fail-closed
PHASE_9_DEFAULT_MODEL=llama-3.3-70b-versatile
PHASE_9_HIGH_STAKES_MODEL=llama-3.3-70b-versatile
PHASE_9_AUTO_TRIGGER_SCORE=60           # auto-investigate score >= this
PHASE_9_MAX_TOOL_ROUNDS=8
PHASE_9_MAX_OUTPUT_TOKENS=1500
PHASE_9_TIMEOUT_SEC=30
GROQ_API_KEY=<your key>                 # already configured in .env
```

### Honest caveats
* Model accuracy is bounded by the prompt and tools — not by ML
  performance.  The agent doesn't "know" anything our XGBoost / SHAP
  layer didn't already surface; it explains and contextualises.
* Tool data quality is the bottleneck.  `MerchantLookupTool` reads from
  our own transactions table (no third-party reputation feed yet);
  `GeoVelocityTool` is heuristic (no lat/long, just location strings).
* Until we collect more labelled fraud, the LLM's hit-rate on the
  `fraud_confirmed` decision will be low — by design (confidence floor).

### Rollback plan
* Soft (instant): set `PHASE_9_AGENT_ENABLED=false` and reload.
* Hard: `git revert <phase-9 commit>` — schema migration is forward-only
  but the tables are append-only; leaving them in place is safe.

---

## Phase 10 — Graph Neural Network (GNN)
**Status:** queued (not started this milestone).
Train a GraphSAGE model over the existing user/device/IP/merchant graph
and serve 64-dim user embeddings to the Phase 3 hybrid scorer via Redis.

## Phase 11 — DNN Migration Path
**Status:** queued.
Multi-branch DNN inspired by Stripe Radar, shadow-deployed via Phase 5
MLflow.  Promote only after 24 h of non-regression on every segment.

## Phase 12 — Multi-Model Orchestrator (LLM-as-Judge)
**Status:** queued.
Single decision-maker that routes between rules / hybrid / GNN / DNN /
LLM agent paths and uses an LLM as a judge for borderline cases.
