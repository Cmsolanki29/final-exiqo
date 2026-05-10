-- Phase 12: Multi-Model Orchestrator (LLM-as-Judge)
--
-- One row per orchestrated decision.  The orchestrator wraps the
-- existing HybridScorer + DecisionEngine and *adds* a tier label
-- (which models contributed) plus, optionally, a Phase 9 investigation
-- and an LLM-as-Judge cross-check.  This table is the audit trail.
--
-- Rollback: DROP TABLE IF EXISTS orchestration_decisions CASCADE;

CREATE TABLE IF NOT EXISTS orchestration_decisions (
    id                    UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id        INTEGER      NULL,
    user_id               INTEGER      NULL,

    -- Routing
    tier                  VARCHAR(20)  NOT NULL,
    routing_reason        TEXT         NOT NULL DEFAULT '',

    -- Baseline (HybridScorer + DecisionEngine) snapshot
    baseline_score        INTEGER      NOT NULL,
    baseline_action       VARCHAR(20)  NOT NULL,
    baseline_reasons      JSONB        NOT NULL DEFAULT '[]'::jsonb,
    baseline_overrides    JSONB        NOT NULL DEFAULT '[]'::jsonb,

    -- Final action (may differ from baseline if judge / investigation overrode)
    final_action          VARCHAR(20)  NOT NULL,
    final_reasons         JSONB        NOT NULL DEFAULT '[]'::jsonb,

    -- Phase 9 investigation hook (NULL if not triggered)
    investigation_id      UUID         NULL,
    investigation_decision VARCHAR(20) NULL,

    -- LLM-as-Judge result (NULL if not invoked)
    judge_invoked         BOOLEAN      NOT NULL DEFAULT FALSE,
    judge_agree           BOOLEAN      NULL,
    judge_confidence      REAL         NULL,
    judge_concerns        JSONB        NOT NULL DEFAULT '[]'::jsonb,
    judge_suggested_action VARCHAR(20) NULL,
    judge_narrative       TEXT         NOT NULL DEFAULT '',
    judge_model           VARCHAR(80)  NOT NULL DEFAULT '',
    judge_input_tokens    INTEGER      NOT NULL DEFAULT 0,
    judge_output_tokens   INTEGER      NOT NULL DEFAULT 0,
    judge_cost_usd        NUMERIC(10,6) NOT NULL DEFAULT 0.0,

    -- Telemetry
    total_latency_ms      INTEGER      NOT NULL DEFAULT 0,
    error                 TEXT         NULL,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orch_txn      ON orchestration_decisions (transaction_id);
CREATE INDEX IF NOT EXISTS idx_orch_user_t   ON orchestration_decisions (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orch_tier_t   ON orchestration_decisions (tier, created_at DESC);

COMMENT ON TABLE orchestration_decisions IS
    'Phase 12: per-transaction orchestration audit trail. Tier indicates which '
    'models contributed; investigation_id and judge_* columns capture optional '
    'LLM augmentations.  This table is the source of truth for the analytics '
    'on /api/risk/orchestrator/tiers/distribution.';
