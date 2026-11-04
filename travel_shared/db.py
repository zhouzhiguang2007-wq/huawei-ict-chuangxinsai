"""Unified SQLite database for the travel-planner plugin's internal private store.

Three logical modules share one database file:
  - travel_knowledge: pre-filled domain facts (city, transport, budget, etc.)
  - session_context: per-trip interaction state and intermediate results
  - skill_registry: detailed skill capability metadata for discovery

The database is intended for a trusted plugin backend. This module does not
serve it over a network; the host controls access. It lives at a configurable
path and is created automatically on first access.
"""

import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(
    os.environ.get("TRAVEL_INTERNAL_DB", "~/.travel-planner/internal.sqlite3")
).expanduser()

# Old session rows have no trustworthy owner. They remain in the upgraded
# database for an administrator to assign after checking their provenance,
# but no SessionStore caller can select this reserved identity.
LEGACY_SESSION_OWNER = "\x00legacy-unassigned"

SCHEMA = """
-- Module A: travel domain knowledge (pre-filled facts)
CREATE TABLE IF NOT EXISTS travel_knowledge (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT NOT NULL,
    key         TEXT NOT NULL,
    value_json  TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'seed',
    updated_at  TEXT NOT NULL,
    UNIQUE(category, key)
);

-- Module B is initialized separately so ownerless legacy rows can be quarantined.
-- Module C: skill capability registry (for agent discovery)
CREATE TABLE IF NOT EXISTS skill_registry (
    skill_name      TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    category        TEXT NOT NULL,
    trigger_keywords TEXT NOT NULL,   -- JSON array
    description     TEXT NOT NULL,
    dependencies    TEXT,             -- JSON array of skill names
    output_summary  TEXT,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_knowledge_category ON travel_knowledge(category);
"""

SESSION_DDL = (
    """CREATE TABLE IF NOT EXISTS session_context (
        user_id     TEXT NOT NULL,
        trip_id     TEXT NOT NULL,
        skill       TEXT NOT NULL,
        stage       TEXT NOT NULL,
        key         TEXT NOT NULL,
        value_json  TEXT NOT NULL,
        created_at  TEXT NOT NULL,
        PRIMARY KEY (user_id, trip_id, skill, stage, key)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_session_owner_trip "
    "ON session_context(user_id, trip_id)",
    "CREATE INDEX IF NOT EXISTS idx_session_owner_skill "
    "ON session_context(user_id, trip_id, skill)",
)


def _ensure_session_schema(conn):
    """Atomically upgrade ownerless sessions without assigning them to users."""
    if "user_id" in {row[1] for row in conn.execute("PRAGMA table_info(session_context)")}:
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        old = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='session_context'"
        ).fetchone()
        needs_migration = bool(old) and "user_id" not in {
            row[1] for row in conn.execute("PRAGMA table_info(session_context)")
        }
        if needs_migration:
            conn.execute("ALTER TABLE session_context RENAME TO session_context_legacy")
        for statement in SESSION_DDL:
            conn.execute(statement)
        if needs_migration:
            conn.execute(
                "INSERT INTO session_context "
                "(user_id, trip_id, skill, stage, key, value_json, created_at) "
                "SELECT ?, trip_id, skill, stage, key, value_json, created_at "
                "FROM session_context_legacy",
                (LEGACY_SESSION_OWNER,),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def get_connection(db_path=None):
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        conn.executescript(SCHEMA)
        _ensure_session_schema(conn)
        return conn
    except Exception:
        conn.close()
        raise


def init_db(db_path=None):
    conn = get_connection(db_path)
    conn.close()
