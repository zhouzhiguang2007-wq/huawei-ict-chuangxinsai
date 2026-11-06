"""Module B: Per-trip session context store.

Stores interaction state (requirement analysis answers) and intermediate
results (candidate spots, weather data, accommodation options) keyed by
trip_id.  Downstream skills read from here instead of re-asking the user.

每条记录都归属一个 `user_id`（来自宿主可信身份，不来自模型文本）。查询、
写入、删除与行程列表都按 user_id 隔离，避免多用户共用 trip_id 时串数据。
为兼容旧的直接调用，方法参数 `user_id=None` 表示不做用户过滤。
"""

import json
from datetime import datetime, timezone
from .db import get_connection


class SessionStore:

    def __init__(self, db_path=None):
        self.db_path = db_path

    def put(self, trip_id, skill, stage, key, value, user_id=None):
        """Store a context entry for a trip, owned by user_id."""
        owner = user_id or ""
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO session_context "
                    "(user_id, trip_id, skill, stage, key, value_json, created_at) "
                    "VALUES (?,?,?,?,?,?,?) "
                    "ON CONFLICT(user_id, trip_id, skill, stage, key) DO UPDATE SET "
                    "value_json=excluded.value_json, created_at=excluded.created_at",
                    (owner, trip_id, skill, stage, key,
                     json.dumps(value, ensure_ascii=False), now),
                )
            return {"user_id": owner, "trip_id": trip_id, "skill": skill,
                    "stage": stage, "key": key, "status": "stored"}
        finally:
            conn.close()

    def get(self, trip_id, skill=None, stage=None, key=None, user_id=None):
        """Retrieve context entries.

        `user_id` 非 None 时只返回该用户的记录；None 表示不过滤（兼容旧调用）。
        """
        conn = get_connection(self.db_path)
        try:
            if user_id is None:
                sql = ("SELECT skill, stage, key, value_json, created_at "
                       "FROM session_context WHERE trip_id=?")
                params = [trip_id]
            else:
                sql = ("SELECT skill, stage, key, value_json, created_at "
                       "FROM session_context WHERE user_id=? AND trip_id=?")
                params = [user_id, trip_id]
            if skill:
                sql += " AND skill=?"
                params.append(skill)
            if stage:
                sql += " AND stage=?"
                params.append(stage)
            if key:
                sql += " AND key=?"
                params.append(key)
            sql += " ORDER BY skill, stage, key"
            rows = conn.execute(sql, params).fetchall()
            entries = []
            for r in rows:
                entries.append({"skill": r[0], "stage": r[1], "key": r[2],
                                "value": json.loads(r[3]), "created_at": r[4]})
            return {"trip_id": trip_id, "entries": entries,
                    "count": len(entries)}
        finally:
            conn.close()

    def get_stage(self, trip_id, skill, stage, user_id=None):
        """Get all key-value pairs for a specific skill+stage of a trip."""
        return self.get(trip_id, skill=skill, stage=stage, user_id=user_id)

    def get_requirements(self, trip_id, user_id=None):
        """Convenience: get the confirmed requirements for a trip."""
        result = self.get(trip_id, skill="travel-requirement-analysis",
                          stage="confirmed", user_id=user_id)
        if not result["entries"]:
            return {"found": False}
        req_entry = None
        for e in result["entries"]:
            if e["key"] == "requirements":
                req_entry = e
                break
        if not req_entry:
            return {"found": False}
        return {"found": True, "requirements": req_entry["value"],
                "created_at": req_entry["created_at"]}

    def list_trips(self, user_id=None):
        """List trip_ids that have context entries (scoped to user when given)."""
        conn = get_connection(self.db_path)
        try:
            if user_id is None:
                rows = conn.execute(
                    "SELECT DISTINCT trip_id FROM session_context ORDER BY trip_id",
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT DISTINCT trip_id FROM session_context "
                    "WHERE user_id=? ORDER BY trip_id",
                    (user_id,),
                ).fetchall()
            return {"trips": [r[0] for r in rows]}
        finally:
            conn.close()

    def clear_trip(self, trip_id, user_id=None):
        """Delete context entries for a trip (scoped to user when given)."""
        conn = get_connection(self.db_path)
        try:
            with conn:
                if user_id is None:
                    result = conn.execute(
                        "DELETE FROM session_context WHERE trip_id=?",
                        (trip_id,),
                    )
                else:
                    result = conn.execute(
                        "DELETE FROM session_context WHERE user_id=? AND trip_id=?",
                        (user_id, trip_id),
                    )
            return {"trip_id": trip_id, "deleted": result.rowcount}
        finally:
            conn.close()

    def clear_stage(self, trip_id, skill, stage, user_id=None):
        """Delete context entries for a skill+stage of a trip."""
        conn = get_connection(self.db_path)
        try:
            with conn:
                if user_id is None:
                    result = conn.execute(
                        "DELETE FROM session_context "
                        "WHERE trip_id=? AND skill=? AND stage=?",
                        (trip_id, skill, stage),
                    )
                else:
                    result = conn.execute(
                        "DELETE FROM session_context "
                        "WHERE user_id=? AND trip_id=? AND skill=? AND stage=?",
                        (user_id, trip_id, skill, stage),
                    )
            return {"trip_id": trip_id, "skill": skill, "stage": stage,
                    "deleted": result.rowcount}
        finally:
            conn.close()