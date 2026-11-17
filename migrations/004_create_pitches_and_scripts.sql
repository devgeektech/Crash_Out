-- Migration: 004_create_pitches_and_scripts.sql
-- Description: Pitches (with is_selected toggle) and Scripts (for 4 video scenes per episode)

CREATE TABLE IF NOT EXISTS pitches (
    id SERIAL PRIMARY KEY,
    episode_id VARCHAR(100) REFERENCES episodes(id) ON DELETE CASCADE,
    pitch_number INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    hook TEXT DEFAULT '',
    synopsis TEXT DEFAULT '',
    target_audience VARCHAR(255) DEFAULT '',
    merch_idea TEXT DEFAULT '',
    is_selected BOOLEAN NOT NULL DEFAULT FALSE,
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pitches_episode ON pitches(episode_id);
CREATE INDEX IF NOT EXISTS idx_pitches_selected ON pitches(is_selected);

CREATE TABLE IF NOT EXISTS scripts (
    id SERIAL PRIMARY KEY,
    episode_id VARCHAR(100) NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    video_number INTEGER NOT NULL,
    scene_title VARCHAR(255) NOT NULL DEFAULT '',
    character VARCHAR(100) DEFAULT '',
    dialogue TEXT DEFAULT '',
    visual_prompt TEXT DEFAULT '',
    audio_prompt TEXT DEFAULT '',
    duration_sec INTEGER DEFAULT 15,
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scripts_episode ON scripts(episode_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_scripts_ep_video ON scripts(episode_id, video_number);

-- Backward compatibility view
CREATE OR REPLACE VIEW script AS SELECT * FROM scripts;
