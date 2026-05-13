-- Subscription Intelligence platform extensions (connected apps, insight feed, audit, accountability).
-- Extends 021 without duplicating app_usage_signals / device_links core.

ALTER TABLE subscriptions
  ADD COLUMN IF NOT EXISTS reminder_escalation_tier SMALLINT NOT NULL DEFAULT 1;

ALTER TABLE reminder_outcomes
  ADD COLUMN IF NOT EXISTS accountability_reason TEXT;

CREATE TABLE IF NOT EXISTS connected_apps (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  app_package VARCHAR(255) NOT NULL,
  display_label VARCHAR(160),
  link_status VARCHAR(20) NOT NULL DEFAULT 'active',
  device_link_id INTEGER REFERENCES device_links(id) ON DELETE SET NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, app_package)
);

CREATE INDEX IF NOT EXISTS idx_connected_apps_user_status ON connected_apps (user_id, link_status);

CREATE TABLE IF NOT EXISTS subscription_events (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  subscription_id INTEGER REFERENCES subscriptions(id) ON DELETE SET NULL,
  event_type VARCHAR(80) NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subscription_events_user_time ON subscription_events (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS subscription_intelligence_insights (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  subscription_id INTEGER REFERENCES subscriptions(id) ON DELETE SET NULL,
  dedupe_key VARCHAR(220) NOT NULL,
  insight_type VARCHAR(40) NOT NULL,
  title VARCHAR(240) NOT NULL,
  body TEXT NOT NULL,
  priority SMALLINT NOT NULL DEFAULT 2,
  read_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, dedupe_key)
);

CREATE INDEX IF NOT EXISTS idx_intel_insights_user_unread ON subscription_intelligence_insights (user_id, read_at NULLS FIRST, priority ASC, created_at DESC);
