-- User-defined important dates (birthdays, anniversaries, etc.) for Festival Planner timeline

CREATE TABLE IF NOT EXISTS user_important_days (
  id               SERIAL PRIMARY KEY,
  user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title            VARCHAR(200) NOT NULL,
  event_date       DATE NOT NULL,
  notes            TEXT,
  repeats_yearly   BOOLEAN NOT NULL DEFAULT FALSE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_important_days_user_id ON user_important_days(user_id);
CREATE INDEX IF NOT EXISTS idx_user_important_days_event_date ON user_important_days(event_date);
