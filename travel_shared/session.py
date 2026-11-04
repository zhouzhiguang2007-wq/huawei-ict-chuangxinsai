"""Module B: Per-trip session context store.

Stores interaction state (requirement analysis answers) and intermediate
results (candidate spots, weather data, accommodation options) keyed by
trusted user_id and trip_id. Downstream skills read only their user's trip.
"""

import json
from datetime import datetime, timezone
from .db import get_connection


class SessionStore:

    def __init__(self, db_path=None):
        self.db_path = db_path

    @staticmethod
    def _owner(user_id):
        if not isinstance(user_id, str) or "\x00" in user_id:
            raise ValueError("user_id must be a string without NUL characters")
        return user_id

    def put(self, trip_id, skill, stage, key, value, *, user_id=""):
        """Store a context entry for a trip."""
        owner = self._owner(user_id)
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
            return {"trip_id": trip_id, "skill": skill, "stage": stage,
                    "key": key, "status": "stored"}
        finally:
            conn.close()

    def get(self, trip_id, skill=None, stage=None, key=None, *, user_id=""):
        """Retrieve context entries. Returns all matching if skill/stage/key are None."""
        owner = self._owner(user_id)
        conn = get_connection(self.db_path)
        try:
            sql = ("SELECT skill, stage, key, value_json, created_at "
                   "FROM session_context WHERE user_id=? AND trip_id=?")
            params = [owner, trip_id]
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

    def get_stage(self, trip_id, skill, stage, *, user_id=""):
        """Get all key-value pairs for a specific skill+stage of a trip."""
        return self.get(trip_id, skill=skill, stage=stage, user_id=user_id)

    def get_requirements(self, trip_id, *, user_id=""):
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

    def list_trips(self, *, user_id=""):
        """List only this user's trip_ids."""
        owner = self._owner(user_id)
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT DISTINCT trip_id FROM session_context "
                "WHERE user_id=? ORDER BY trip_id",
                (owner,),
            ).fetchall()
            return {"trips": [r[0] for r in rows]}
        finally:
            conn.close()

    def clear_trip(self, trip_id, *, user_id=""):
        """Delete this user's context entries for a trip."""
        owner = self._owner(user_id)
        conn = get_connection(self.db_path)
        try:
            with conn:
                result = conn.execute(
                    "DELETE FROM session_context WHERE user_id=? AND trip_id=?",
                    (owner, trip_id),
                )
            return {"trip_id": trip_id, "deleted": result.rowcount}
        finally:
            conn.close()

    def clear_stage(self, trip_id, skill, stage, *, user_id=""):
        """Delete this user's entries for a specific skill and stage."""
        owner = self._owner(user_id)
        conn = get_connection(self.db_path)
        try:
            with conn:
                result = conn.execute(
                    "DELETE FROM session_context "
                    "WHERE user_id=? AND trip_id=? AND skill=? AND stage=?",
                    (owner, trip_id, skill, stage),
                )
            return {"trip_id": trip_id, "skill": skill, "stage": stage,
                    "deleted": result.rowcount}
        finally:
            conn.close()
