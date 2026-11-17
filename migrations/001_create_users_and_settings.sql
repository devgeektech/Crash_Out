-- Migration: 001_create_users_and_settings.sql
-- Description: Core user authentication and encrypted user settings tables

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name VARCHAR(255) NOT NULL DEFAULT '',
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    vidu_api_key_enc TEXT NOT NULL DEFAULT '',
    vidu_email VARCHAR(255) NOT NULL DEFAULT '',
    vidu_model VARCHAR(100) NOT NULL DEFAULT '',
    vidu_reference_model VARCHAR(100) NOT NULL DEFAULT '',
    vidu_resolution VARCHAR(50) NOT NULL DEFAULT '',
    updated_at DOUBLE PRECISION NOT NULL
);
