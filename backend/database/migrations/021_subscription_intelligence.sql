-- Subscription Intelligence: device usage signals, verdicts, substitutions, reminders.
-- SIMULATED: real impl ingests Android UsageStatsManager via companion mobile SDK (see device_links).

ALTER TABLE subscriptions
  ADD COLUMN IF NOT EXISTS intelligence_category VARCHAR(40) DEFAULT 'other',
  ADD COLUMN IF NOT EXISTS linked_app_package VARCHAR(255),
  ADD COLUMN IF NOT EXISTS sub_lifecycle VARCHAR(20) DEFAULT 'active',
  ADD COLUMN IF NOT EXISTS billing_day SMALLINT,
  ADD COLUMN IF NOT EXISTS next_billing_date DATE,
  ADD COLUMN IF NOT EXISTS currency VARCHAR(8) DEFAULT 'INR',
  ADD COLUMN IF NOT EXISTS current_verdict VARCHAR(20),
  ADD COLUMN IF NOT EXISTS verdict_confidence INT,
  ADD COLUMN IF NOT EXISTS verdict_reason TEXT,
  ADD COLUMN IF NOT EXISTS verdict_monthly_waste DECIMAL(12,2) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_evaluated_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS is_pro BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_verdict ON subscriptions (user_id, current_verdict);
CREATE INDEX IF NOT EXISTS idx_subscriptions_linked_pkg ON subscriptions (user_id, linked_app_package);

CREATE TABLE IF NOT EXISTS app_usage_signals (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  app_package VARCHAR(255) NOT NULL,
  signal_date DATE NOT NULL,
  usage_minutes INTEGER NOT NULL DEFAULT 0,
  session_count INTEGER NOT NULL DEFAULT 0,
  last_opened_at TIMESTAMPTZ,
  weekend_minutes INTEGER NOT NULL DEFAULT 0,
  peak_hour SMALLINT,
  notifications_received INTEGER NOT NULL DEFAULT 0,
  notifications_opened INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, app_package, signal_date)
);

CREATE INDEX IF NOT EXISTS idx_app_usage_user_date ON app_usage_signals (user_id, signal_date);
CREATE INDEX IF NOT EXISTS idx_app_usage_pkg ON app_usage_signals (user_id, app_package);

CREATE TABLE IF NOT EXISTS subscription_substitutions (
  id SERIAL PRIMARY KEY,
  category VARCHAR(40) NOT NULL,
  primary_app VARCHAR(255) NOT NULL,
  substitute_apps JSONB NOT NULL DEFAULT '[]'::jsonb,
  category_display_name VARCHAR(120) NOT NULL,
  UNIQUE (category, primary_app)
);

CREATE TABLE IF NOT EXISTS verdict_history (
  id SERIAL PRIMARY KEY,
  subscription_id INTEGER NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
  evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  verdict VARCHAR(20) NOT NULL,
  usage_delta_30d DOUBLE PRECISION,
  confidence INT NOT NULL,
  reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_verdict_hist_sub ON verdict_history (subscription_id, evaluated_at DESC);

CREATE TABLE IF NOT EXISTS scheduled_reminders (
  id SERIAL PRIMARY KEY,
  subscription_id INTEGER NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  fire_at TIMESTAMPTZ NOT NULL,
  reminder_type VARCHAR(10) NOT NULL,
  state VARCHAR(20) NOT NULL DEFAULT 'pending',
  escalation_level INTEGER NOT NULL DEFAULT 1,
  shown_at TIMESTAMPTZ,
  acted_at TIMESTAMPTZ,
  user_action VARCHAR(20)
);

CREATE INDEX IF NOT EXISTS idx_sched_rem_user_fire ON scheduled_reminders (user_id, state, fire_at);

CREATE TABLE IF NOT EXISTS reminder_outcomes (
  id SERIAL PRIMARY KEY,
  reminder_id INTEGER NOT NULL REFERENCES scheduled_reminders(id) ON DELETE CASCADE,
  subscription_id INTEGER NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  user_action VARCHAR(20) NOT NULL,
  cancelled_within_7d BOOLEAN NOT NULL DEFAULT FALSE,
  effectiveness_score INTEGER NOT NULL DEFAULT 50,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS device_links (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  device_type VARCHAR(20) NOT NULL DEFAULT 'simulated',
  permissions JSONB NOT NULL DEFAULT '{}'::jsonb,
  apps_linked JSONB NOT NULL DEFAULT '[]'::jsonb,
  link_status VARCHAR(20) NOT NULL DEFAULT 'active',
  UNIQUE (user_id)
);

INSERT INTO subscription_substitutions (category, primary_app, substitute_apps, category_display_name)
VALUES
  ('music', 'com.spotify.music', '["com.google.android.apps.youtube.music", "com.apple.android.music"]'::jsonb, 'Music Streaming'),
  ('video', 'com.netflix.mediaclient', '["in.amazon.mShop.android.shopping", "in.startv.hotstar"]'::jsonb, 'Video Streaming'),
  ('professional', 'com.linkedin.android', '["com.openai.chatgpt", "com.linkedin.android.lite"]'::jsonb, 'Professional'),
  ('productivity', 'com.canva.editor', '["com.openai.chatgpt", "com.notion.android"]'::jsonb, 'Productivity')
ON CONFLICT (category, primary_app) DO NOTHING;
