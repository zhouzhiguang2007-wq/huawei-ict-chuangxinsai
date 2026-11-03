"""Unified SQLite database for the travel-planner plugin's internal private store.

Three logical modules share one database file:
  - travel_knowledge: pre-filled domain facts (city, transport, budget, etc.)
  - session_context: per-trip interaction state and intermediate results
  - skill_registry: detailed skill capability metadata for discovery

The database is plugin-internal: not exposed to external systems, not synced
to any cloud knowledge base.  It lives at a configurable path and is created
automatically on first access.
"""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".travel-planner" / "internal.sqlite3"

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

-- Module B: per-trip session context (interaction state + intermediate results)
CREATE TABLE IF NOT EXISTS session_context (
    trip_id     TEXT NOT NULL,
    skill       TEXT NOT NULL,
    stage       TEXT NOT NULL,
    key         TEXT NOT NULL,
    value_json  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (trip_id, skill, stage, key)
);

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
CREATE INDEX IF NOT EXISTS idx_session_trip ON session_context(trip_id);
CREATE INDEX IF NOT EXISTS idx_session_skill ON session_context(trip_id, skill);
"""


def get_connection(db_path=None):
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def init_db(db_path=None):
    conn = get_connection(db_path)
    conn.close()