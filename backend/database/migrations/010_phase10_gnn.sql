-- Phase 10: Graph Neural Network (heterogeneous GraphSAGE)
--
-- Two tables:
--   gnn_user_embeddings  — durable storage for the latest user embedding
--                          (Redis is the fast path; this table is the
--                          fallback when Redis is unavailable, and the
--                          source of truth across restarts).
--   gnn_training_runs    — one row per call to train_gnn(); used by the
--                          admin /train endpoint to render the loss
--                          curve and the model card.

CREATE TABLE IF NOT EXISTS gnn_user_embeddings (
    user_id        INTEGER     PRIMARY KEY,
    -- pgvector would be ideal but we keep it portable: REAL[] of length embed_dim.
    embedding      REAL[]      NOT NULL,
    embed_dim      INTEGER     NOT NULL,
    model_version  VARCHAR(40) NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gnn_emb_version
    ON gnn_user_embeddings (model_version);

COMMENT ON TABLE gnn_user_embeddings IS
    'Phase 10: latest GraphSAGE user embedding.  One row per user.';

CREATE TABLE IF NOT EXISTS gnn_training_runs (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    model_version    VARCHAR(40)  NOT NULL,

    -- Graph snapshot stats
    num_users        INTEGER      NOT NULL DEFAULT 0,
    num_merchants    INTEGER      NOT NULL DEFAULT 0,
    edge_counts      JSONB        NOT NULL DEFAULT '{}'::jsonb,
    label_source     VARCHAR(40)  NOT NULL DEFAULT 'anomaly_flag',
    labelled_users   INTEGER      NOT NULL DEFAULT 0,
    txn_window_days  INTEGER      NOT NULL DEFAULT 0,

    -- Hyperparameters
    embed_dim        INTEGER      NOT NULL,
    num_layers       INTEGER      NOT NULL,
    epochs           INTEGER      NOT NULL,
    lr               REAL         NOT NULL,

    -- Outcome
    final_loss       REAL         NULL,
    sup_loss         REAL         NULL,
    unsup_loss       REAL         NULL,
    train_acc        REAL         NULL,
    loss_history     JSONB        NOT NULL DEFAULT '[]'::jsonb,
    embeddings_written INTEGER    NOT NULL DEFAULT 0,
    duration_sec     REAL         NOT NULL DEFAULT 0,
    error            TEXT         NULL,

    started_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    completed_at     TIMESTAMPTZ  NULL
);

CREATE INDEX IF NOT EXISTS idx_gnn_runs_started
    ON gnn_training_runs (started_at DESC);

COMMENT ON TABLE gnn_training_runs IS
    'Phase 10: history of GNN training runs with hyperparams and outcome.';
