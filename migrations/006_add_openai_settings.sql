-- Migration: 006_add_openai_settings.sql
-- Description: Add encrypted OpenAI API key and model selection to user_settings

ALTER TABLE user_settings
    ADD COLUMN IF NOT EXISTS openai_api_key_enc TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS openai_model VARCHAR(100) NOT NULL DEFAULT '';
