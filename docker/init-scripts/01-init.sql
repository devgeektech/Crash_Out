-- ============================================================================
-- Initialization script for Crash Out: PostgreSQL + pgvector + Temporal
-- ============================================================================

-- 1. Setup pgvector in app_db
\c app_db;
CREATE EXTENSION IF NOT EXISTS vector;

-- Agent 0 & Pitch Uniqueness Tables
CREATE TABLE IF NOT EXISTS generated_pitches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_date TEXT NOT NULL,
    rank INT,
    headline TEXT NOT NULL,
    youth_sentiment_summary TEXT,
    crash_out_angle TEXT NOT NULL,
    proposed_merch_hook TEXT,
    sensitivity_flag TEXT DEFAULT 'SAFE',
    consensus_score FLOAT DEFAULT 0.0,
    sources JSONB,
    score_breakdown JSONB,
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pitches_embedding 
ON generated_pitches USING hnsw (embedding vector_cosine_ops);

-- S3 Video Assets Tracking Table
CREATE TABLE IF NOT EXISTS video_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    episode_id TEXT,
    scene_index INT,
    s3_bucket TEXT NOT NULL,
    s3_key TEXT NOT NULL,
    s3_url TEXT,
    file_type TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Notifications & Push Tracking Table
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    category VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    deep_link VARCHAR(500) NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    telegram_sent BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Databases required for Temporal engine persistence
CREATE DATABASE temporal;
CREATE DATABASE temporal_visibility;
