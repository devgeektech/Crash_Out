-- Migration: 005_create_notifications_and_user_notification_settings.sql
-- Description: Real-Time Mobile Push Notifications, Telegram Bot Integration & User Preferences

-- 1. Extend user_settings with Telegram bot credentials & notification preferences
ALTER TABLE user_settings 
    ADD COLUMN IF NOT EXISTS telegram_bot_token_enc TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(100) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS telegram_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS notify_hitl BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS notify_errors BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS notify_published BOOLEAN NOT NULL DEFAULT TRUE;

-- 2. Create notifications table for in-app bell feed, mobile push history, and deep-link routing
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL, -- 'hitl', 'error', 'published', 'system'
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    deep_link VARCHAR(500) NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    telegram_sent BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_created ON notifications(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_category ON notifications(category);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read);
