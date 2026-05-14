-- SmartSpend Phase 24: AI Chatbot — sessions, persistent message history, document uploads.
-- All tables are additive — no existing tables are modified except two optional columns on transactions.

-- ── AI chat sessions ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  started_at TIMESTAMPTZ DEFAULT NOW(),
  last_active TIMESTAMPTZ DEFAULT NOW(),
  session_context JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_ai_sessions_user_id ON ai_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_sessions_last_active ON ai_sessions(last_active);

-- ── AI chat messages (persistent history) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES ai_sessions(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  message TEXT NOT NULL,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_messages_session_id ON ai_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_ai_messages_created_at ON ai_messages(session_id, created_at);

-- ── Uploaded documents (expire 24 h, cleaned up lazily) ───────────────────
CREATE TABLE IF NOT EXISTS document_uploads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  session_id UUID REFERENCES ai_sessions(id) ON DELETE CASCADE,
  file_name TEXT NOT NULL,
  document_type TEXT,        -- 'bank_statement' | 'credit_card' | 'emi_schedule' | 'upi_history' | 'other'
  institution TEXT,          -- detected bank name e.g. 'SBI', 'ICICI', 'HDFC'
  is_linked_account BOOLEAN DEFAULT FALSE,
  parsed_text TEXT,
  extracted_json JSONB,
  uploaded_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '24 hours')
);

CREATE INDEX IF NOT EXISTS idx_doc_uploads_user_session ON document_uploads(user_id, session_id);
CREATE INDEX IF NOT EXISTS idx_doc_uploads_expires_at ON document_uploads(expires_at);

-- ── Optional columns on transactions for uploaded-doc origin ─────────────
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS document_origin TEXT DEFAULT 'linked_bank';
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS source_document_id UUID REFERENCES document_uploads(id);
