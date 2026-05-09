-- SmartSpend Phase 2: bank connections (mock Account Aggregator)

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
