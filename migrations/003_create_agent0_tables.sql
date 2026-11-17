-- Migration: 003_create_agent0_tables.sql
-- Description: Agent 0 trend scraper runs, raw scraped items, and 30-day topic deduplication

CREATE TABLE IF NOT EXISTS agent0_pitch_runs (
    id SERIAL PRIMARY KEY,
    run_date TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent0_pitch_runs_date ON agent0_pitch_runs(run_date);
CREATE INDEX IF NOT EXISTS idx_agent0_pitch_runs_created ON agent0_pitch_runs(created_at);

CREATE TABLE IF NOT EXISTS agent0_raw_items (
    id SERIAL PRIMARY KEY,
    run_date TEXT NOT NULL,
    layer TEXT,
    title TEXT,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent0_raw_items_date ON agent0_raw_items(run_date);

CREATE TABLE IF NOT EXISTS agent0_episode_topics (
    episode_id TEXT PRIMARY KEY,
    title TEXT,
    label TEXT,
    embedding TEXT,
    label_text TEXT,
    approved_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent0_topics_approved ON agent0_episode_topics(approved_at);
