"""
Database Migrations Manager for Crash Out.
Tracks schema changes in the `schema_migrations` table with version history and timestamps.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List

from app.db import get_conn
from app.paths import PROJECT_ROOT

logger = logging.getLogger("app.migrations")

MIGRATIONS_DIR = os.path.join(PROJECT_ROOT, "migrations")


def ensure_migration_table() -> None:
    """Ensure the schema_migrations tracking table exists."""
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(100) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                applied_at TIMESTAMPTZ DEFAULT NOW(),
                execution_time_ms INTEGER NOT NULL DEFAULT 0
            );
            """
        )


def get_applied_migrations() -> Dict[str, Dict[str, Any]]:
    """Return dictionary of applied migration records keyed by version."""
    ensure_migration_table()
    with get_conn() as conn:
        res = conn.execute("SELECT version, name, applied_at, execution_time_ms FROM schema_migrations ORDER BY version")
        return {row["version"]: dict(row) for row in res.fetchall()}


def run_migrations() -> List[Dict[str, Any]]:
    """
    Find and execute all unapplied SQL migration files in order.
    Returns list of newly applied migrations.
    """
    ensure_migration_table()
    applied = get_applied_migrations()

    if not os.path.isdir(MIGRATIONS_DIR):
        logger.warning("Migrations directory not found at %s", MIGRATIONS_DIR)
        return []

    sql_files = sorted(
        [f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql")]
    )

    newly_applied = []

    for filename in sql_files:
        version = filename.split("_", 1)[0]
        if version in applied:
            continue

        file_path = os.path.join(MIGRATIONS_DIR, filename)
        logger.info("Applying migration %s (%s)...", version, filename)

        with open(file_path, "r", encoding="utf-8") as f:
            sql_content = f.read()

        start_time = time.time()
        with get_conn() as conn:
            conn.executescript(sql_content)
            elapsed_ms = int((time.time() - start_time) * 1000)

            conn.execute(
                """
                INSERT INTO schema_migrations (version, name, applied_at, execution_time_ms)
                VALUES (?, ?, NOW(), ?)
                """,
                (version, filename, elapsed_ms),
            )

        record = {
            "version": version,
            "name": filename,
            "execution_time_ms": elapsed_ms,
        }
        newly_applied.append(record)
        logger.info("Applied migration %s in %d ms.", filename, elapsed_ms)

    return newly_applied


def get_migration_history() -> List[Dict[str, Any]]:
    """Return full chronological migration history."""
    ensure_migration_table()
    with get_conn() as conn:
        res = conn.execute(
            """
            SELECT version, name, applied_at, execution_time_ms
            FROM schema_migrations
            ORDER BY version ASC
            """
        )
        return res.fetchall()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("Running migrations...")
    new_mig = run_migrations()
    if new_mig:
        print(f"Applied {len(new_mig)} new migration(s):")
        for m in new_mig:
            print(f"  + [{m['version']}] {m['name']} ({m['execution_time_ms']} ms)")
    else:
        print("All migrations are already up to date.")

    print("\nMigration History:")
    history = get_migration_history()
    for h in history:
        print(f"  * {h['version']}: {h['name']} | applied {h['applied_at']} ({h['execution_time_ms']} ms)")
