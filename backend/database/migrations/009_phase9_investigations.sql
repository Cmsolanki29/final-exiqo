-- Phase 9: LLM Investigation Agent
--
-- When a transaction is flagged at risk_score >= 60 OR an analyst manually
-- triggers it, the investigation agent runs a tool-using LLM (Groq Llama)
-- and produces a structured decision + plain-English narrative.
--
-- Two tables:
--   risk_investigations   — one row per investigation run
--   risk_llm_budget_log   — daily LLM spend rollup, drives the fail-closed
--                            budget guard (BudgetGuard.check_and_reserve)
--
-- Both tables are append-only.  No PII is ever stored — see
-- backend/services/risk_common/pii_redactor.py for the redaction layer.

-- ------------------------------------------------------------------ --
-- risk_investigations
-- ------------------------------------------------------------------ --

CREATE TABLE IF NOT EXISTS risk_investigations (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id    INTEGER      NOT NULL,                       -- FK soft (transactions.id)
    user_id           INTEGER      NOT NULL,                       -- FK soft (users.id)

    -- Trigger metadata
    triggered_by      VARCHAR(50)  NOT NULL,                       -- auto_high_risk | analyst_review | manual
    agent_model       VARCHAR(80)  NOT NULL,                       -- llama-3.3-70b-versatile | fallback

    -- Tool execution log (each entry: tool, input, output_summary)
    tool_calls        JSONB        NOT NULL DEFAULT '[]'::jsonb,
    tool_call_count   INTEGER      NOT NULL DEFAULT 0,

    -- Decision output
    decision          VARCHAR(20)  NOT NULL DEFAULT 'inconclusive' -- fraud_confirmed|legitimate|inconclusive
                          CHECK (decision IN ('fraud_confirmed','legitimate','inconclusive')),
    confidence        REAL         NOT NULL DEFAULT 0.0
                          CHECK (confidence >= 0.0 AND confidence <= 1.0),
    narrative         TEXT         NOT NULL DEFAULT '',
    suggested_rules   JSONB        NOT NULL DEFAULT '[]'::jsonb,
    pii_redacted      BOOLEAN      NOT NULL DEFAULT TRUE,

    -- Cost tracking (Groq pricing as of May 2026)
    input_tokens      INTEGER      NOT NULL DEFAULT 0,
    output_tokens     INTEGER      NOT NULL DEFAULT 0,
    cost_usd          NUMERIC(10,6) NOT NULL DEFAULT 0.0,

    -- Timing
    latency_ms        INTEGER      NOT NULL DEFAULT 0,
    rounds_used       INTEGER      NOT NULL DEFAULT 0,
    started_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    completed_at      TIMESTAMPTZ  NULL,

    -- If investigation failed mid-flight
    error             TEXT         NULL
);

CREATE INDEX IF NOT EXISTS idx_inv_txn
    ON risk_investigations (transaction_id);
CREATE INDEX IF NOT EXISTS idx_inv_user
    ON risk_investigations (user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_inv_decision
    ON risk_investigations (decision, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_inv_started
    ON risk_investigations (started_at DESC);

COMMENT ON TABLE risk_investigations IS
    'Phase 9: LLM investigation agent run log.  Each row is one agent execution.';
COMMENT ON COLUMN risk_investigations.decision IS
    'fraud_confirmed = recommend BLOCK; legitimate = recommend ALLOW; inconclusive = HUMAN review';
COMMENT ON COLUMN risk_investigations.tool_calls IS
    'JSONB array of tool execution records (PII-redacted).  Used for audit + debugging.';
COMMENT ON COLUMN risk_investigations.cost_usd IS
    'Actual LLM API spend for this investigation, computed from input/output tokens.';

-- ------------------------------------------------------------------ --
-- risk_llm_budget_log
-- ------------------------------------------------------------------ --

CREATE TABLE IF NOT EXISTS risk_llm_budget_log (
    id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    date            DATE          NOT NULL,
    model           VARCHAR(80)   NOT NULL,
    request_count   INTEGER       NOT NULL DEFAULT 0,
    input_tokens    BIGINT        NOT NULL DEFAULT 0,
    output_tokens   BIGINT        NOT NULL DEFAULT 0,
    cost_usd        NUMERIC(10,4) NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (date, model)
);

CREATE INDEX IF NOT EXISTS idx_budget_date
    ON risk_llm_budget_log (date DESC);

COMMENT ON TABLE risk_llm_budget_log IS
    'Phase 9: daily LLM spend rollup.  Drives BudgetGuard fail-closed cap.';
