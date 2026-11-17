-- Migration: 002_create_episodes_and_audit_logs.sql
-- Description: Core episode management and system audit trail

CREATE TABLE IF NOT EXISTS episodes (
    id VARCHAR(100) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'DRAFT',
    tokens INTEGER NOT NULL DEFAULT 0,
    episode_number INTEGER DEFAULT 0,
    current_gateway INTEGER NOT NULL DEFAULT 1,
    cultural_hook TEXT DEFAULT '',
    merch_punchline TEXT DEFAULT '',
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ensure columns exist in case of prior partial creation
ALTER TABLE episodes ADD COLUMN IF NOT EXISTS tokens INTEGER NOT NULL DEFAULT 0;
ALTER TABLE episodes ADD COLUMN IF NOT EXISTS episode_number INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_episodes_status ON episodes(status);
CREATE INDEX IF NOT EXISTS idx_episodes_created_at ON episodes(created_at);

CREATE TABLE IF NOT EXISTS system_audit_logs (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    actor VARCHAR(100) DEFAULT 'system',
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_event_type ON system_audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON system_audit_logs(created_at);
