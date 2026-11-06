"""Unified SQLite database for the travel-planner plugin's internal private store.

Three logical modules share one database file:
  - travel_knowledge: pre-filled domain facts (city, transport, budget, etc.)
  - session_context: per-trip interaction state and intermediate results
  - skill_registry: detailed skill capability metadata for discovery

The database is plugin-internal: not exposed to external systems, not synced
to any cloud knowledge base.  It lives at a configurable path and is created
automatically on first access.
"""

import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".travel-planner" / "internal.sqlite3"


def default_internal_db_path():
    """内部私有库路径解析。

    优先级：环境变量 `TRAVEL_INTERNAL_DB`，否则 `~/.travel-planner/internal.sqlite3`。
    初始化（seed）与运行时必须使用同一个解析函数，避免“初始化写默认位置、
    启动读自定义位置”的错位。
    """
    return Path(os.environ.get("TRAVEL_INTERNAL_DB", str(DEFAULT_DB_PATH))).expanduser()

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
-- user_id 必填（默认空串兼容旧数据），主键含 user_id，避免多用户同 trip_id 串数据。
CREATE TABLE IF NOT EXISTS session_context (
    user_id     TEXT NOT NULL DEFAULT '',
    trip_id     TEXT NOT NULL,
    skill       TEXT NOT NULL,
    stage       TEXT NOT NULL,
    key         TEXT NOT NULL,
    value_json  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (user_id, trip_id, skill, stage, key)
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

-- Module D: guided questionnaire (proactive user prompting)
CREATE TABLE IF NOT EXISTS guided_questions (
    step            INTEGER PRIMARY KEY,
    dimension       TEXT NOT NULL,
    question        TEXT NOT NULL,
    question_type   TEXT NOT NULL,      -- choice / fill / confirm
    options_json    TEXT,               -- JSON array of {label, description}
    allow_custom    INTEGER NOT NULL DEFAULT 1,
    triggers_skill  TEXT NOT NULL,
    tip             TEXT,
    is_optional     INTEGER NOT NULL DEFAULT 0,
    updated_at      TEXT NOT NULL
);

-- Module E: user preferences are separate from guided question templates.
CREATE TABLE IF NOT EXISTS preferences (
    user_id TEXT NOT NULL, field TEXT NOT NULL, value_json TEXT NOT NULL,
    source TEXT NOT NULL, updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, field)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_category ON travel_knowledge(category);
CREATE INDEX IF NOT EXISTS idx_questions_step ON guided_questions(step);
"""

# session 索引依赖 user_id 列，必须在旧表迁移完成后再创建。
SESSION_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_session_trip ON session_context(user_id, trip_id);
CREATE INDEX IF NOT EXISTS idx_session_skill ON session_context(user_id, trip_id, skill);
"""


def _column_names(conn, table):
    return {row[1] for row in conn.execute("PRAGMA table_info(" + table + ")")}


def _migrate_session_context(conn):
    """把无 user_id 的旧 session_context 迁移为新结构。

    旧库的 `CREATE TABLE IF NOT EXISTS` 不会改已有表结构，因此必须在连接
    建立后显式检测并重建。旧数据统一归到 `user_id=''`，不丢数据。
    """
    if "user_id" in _column_names(conn, "session_context"):
        return
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS session_context_new (
            user_id     TEXT NOT NULL DEFAULT '',
            trip_id     TEXT NOT NULL,
            skill       TEXT NOT NULL,
            stage       TEXT NOT NULL,
            key         TEXT NOT NULL,
            value_json  TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            PRIMARY KEY (user_id, trip_id, skill, stage, key)
        );
        INSERT OR IGNORE INTO session_context_new
            (user_id, trip_id, skill, stage, key, value_json, created_at)
            SELECT '', trip_id, skill, stage, key, value_json, created_at
            FROM session_context;
        DROP TABLE session_context;
        ALTER TABLE session_context_new RENAME TO session_context;

    """)


def get_connection(db_path=None):
    path = Path(db_path) if db_path else default_internal_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    _migrate_session_context(conn)
    conn.executescript(SESSION_INDEXES)
    return conn


def init_db(db_path=None):
    conn = get_connection(db_path)
    conn.close()