"""SQLite implementation. The trusted host supplies the user identity."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .contracts import FIELDS, nonempty, validate_preferences


class PreferenceStore:
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(self.path), timeout=5)
        try:
            db.execute("PRAGMA busy_timeout=5000")
            # Low-write demo: default rollback journal needs no WAL shared memory.
            db.execute("""CREATE TABLE IF NOT EXISTS preferences (
                user_id TEXT NOT NULL, field TEXT NOT NULL, value_json TEXT NOT NULL,
                source TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, field))""")
            return db
        except Exception:
            db.close()
            raise

    def get(self, user_id):
        nonempty(user_id, "trusted user_id")
        db = self._connect()
        try:
            rows = db.execute(
                "SELECT field,value_json,source,updated_at FROM preferences WHERE user_id=? ORDER BY field",
                (user_id,),
            ).fetchall()
            return {"preferences": {k: json.loads(v) for k, v, _, _ in rows},
                    "metadata": {k: {"source": s, "updated_at": t} for k, _, s, t in rows}}
        finally:
            db.close()

    def update(self, user_id, preferences, confirmed, source):
        nonempty(user_id, "trusted user_id")
        if confirmed is not True:
            raise ValueError("persistent writes require explicit user confirmation")
        validate_preferences(preferences, persistent=True)
        if not preferences:
            raise ValueError("update must contain at least one preference")
        nonempty(source, "user confirmation source")
        now = datetime.now(timezone.utc).isoformat()
        db = self._connect()
        try:
            with db:
                db.executemany(
                    "INSERT INTO preferences VALUES (?,?,?,?,?) "
                    "ON CONFLICT(user_id,field) DO UPDATE SET value_json=excluded.value_json, "
                    "source=excluded.source, updated_at=excluded.updated_at",
                    [(user_id, k, json.dumps(v, ensure_ascii=False), source, now)
                     for k, v in preferences.items()],
                )
            return {"updated_fields": sorted(preferences)}
        finally:
            db.close()

    def delete(self, user_id, fields=None):
        nonempty(user_id, "trusted user_id")
        if fields is not None and (not isinstance(fields, list) or not fields
                                   or any(not isinstance(k, str) or k not in FIELDS for k in fields)):
            raise ValueError("fields must be a nonempty list of supported fields")
        db = self._connect()
        try:
            with db:
                if fields is None:
                    result = db.execute("DELETE FROM preferences WHERE user_id=?", (user_id,))
                    count = result.rowcount
                else:
                    count = 0
                    for key in set(fields):
                        count += db.execute("DELETE FROM preferences WHERE user_id=? AND field=?",
                                            (user_id, key)).rowcount
            return {"deleted_count": count}
        finally:
            db.close()
