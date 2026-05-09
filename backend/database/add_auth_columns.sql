-- Manual one-shot: auth columns + sessions + bank_connections (idempotent).
-- Prefer: `python backend/database/run_migration.py` (runs migrations/*.sql in order).

-- === From migrations/001_add_authentication.sql ===
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255),
  ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS last_login TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS sessions (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token TEXT UNIQUE NOT NULL,
  refresh_token TEXT UNIQUE,
  expires_at TIMESTAMP NOT NULL,
  ip_address VARCHAR(45),
  user_agent TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);

-- === From migrations/002_bank_connections.sql ===
CREATE TABLE IF NOT EXISTS bank_connections (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  bank_name VARCHAR(50) NOT NULL,
  account_masked VARCHAR(20),
  connection_status VARCHAR(20) DEFAULT 'connected',
  connected_at TIMESTAMP DEFAULT NOW(),
  last_synced TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE (user_id, bank_name)
);

CREATE INDEX IF NOT EXISTS idx_bank_connections_user ON bank_connections(user_id);
