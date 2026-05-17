-- AI session context cache + upload identity scope (shared across workers via Postgres)
ALTER TABLE ai_sessions ADD COLUMN IF NOT EXISTS cached_context JSONB;
ALTER TABLE ai_sessions ADD COLUMN IF NOT EXISTS context_built_at TIMESTAMPTZ;
ALTER TABLE ai_sessions ADD COLUMN IF NOT EXISTS upload_scope_context JSONB;
ALTER TABLE ai_sessions ADD COLUMN IF NOT EXISTS cache_dashboard_scope TEXT;
ALTER TABLE ai_sessions ADD COLUMN IF NOT EXISTS cache_context_month INTEGER;
ALTER TABLE ai_sessions ADD COLUMN IF NOT EXISTS cache_context_year INTEGER;
