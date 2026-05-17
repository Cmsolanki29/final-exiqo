-- Persistent AI insight cache (survives process restarts / multi-worker)
CREATE TABLE IF NOT EXISTS insight_cache (
    user_id INTEGER NOT NULL,
    month INTEGER NOT NULL,
    year INTEGER NOT NULL,
    scope TEXT NOT NULL DEFAULT 'merged',
    payload JSONB NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, month, year, scope)
);

CREATE INDEX IF NOT EXISTS idx_insight_cache_user_generated
    ON insight_cache (user_id, generated_at);
