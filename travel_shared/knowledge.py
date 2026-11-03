"""Module A: Travel domain knowledge store.

Pre-filled facts that skills query at execution time instead of running empty.
Categories: city_info, intercity_transport, budget_reference, accommodation_type,
local_food, photo_spot, season_tip, transit_tip.
"""

import json
from datetime import datetime, timezone
from .db import get_connection


class KnowledgeStore:

    def __init__(self, db_path=None):
        self.db_path = db_path

    def query(self, category=None, key=None, keyword=None):
        """Query knowledge by category, exact key, or free-text keyword match."""
        conn = get_connection(self.db_path)
        try:
            if category and key:
                row = conn.execute(
                    "SELECT value_json, source, updated_at FROM travel_knowledge "
                    "WHERE category=? AND key=?",
                    (category, key),
                ).fetchone()
                if not row:
                    return {"found": False}
                return {"found": True, "category": category, "key": key,
                        "value": json.loads(row[0]), "source": row[1],
                        "updated_at": row[2]}

            if category:
                rows = conn.execute(
                    "SELECT category, key, value_json, source, updated_at "
                    "FROM travel_knowledge WHERE category=? ORDER BY key",
                    (category,),
                ).fetchall()
            elif keyword:
                pattern = f"%{keyword}%"
                rows = conn.execute(
                    "SELECT category, key, value_json, source, updated_at "
                    "FROM travel_knowledge "
                    "WHERE key LIKE ? OR value_json LIKE ? "
                    "ORDER BY category, key",
                    (pattern, pattern),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT category, key, value_json, source, updated_at "
                    "FROM travel_knowledge ORDER BY category, key",
                ).fetchall()

            results = []
            for r in rows:
                results.append({"category": r[0], "key": r[1],
                                "value": json.loads(r[2]),
                                "source": r[3], "updated_at": r[4]})
            return {"found": bool(results), "results": results}
        finally:
            conn.close()

    def upsert(self, category, key, value, source="seed"):
        """Insert or update a knowledge entry."""
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO travel_knowledge (category, key, value_json, source, updated_at) "
                    "VALUES (?,?,?,?,?) "
                    "ON CONFLICT(category, key) DO UPDATE SET "
                    "value_json=excluded.value_json, source=excluded.source, "
                    "updated_at=excluded.updated_at",
                    (category, key, json.dumps(value, ensure_ascii=False), source, now),
                )
            return {"category": category, "key": key, "status": "upserted"}
        finally:
            conn.close()

    def bulk_upsert(self, entries):
        """Batch insert/update. Each entry: {category, key, value, source?}."""
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.executemany(
                    "INSERT INTO travel_knowledge (category, key, value_json, source, updated_at) "
                    "VALUES (?,?,?,?,?) "
                    "ON CONFLICT(category, key) DO UPDATE SET "
                    "value_json=excluded.value_json, source=excluded.source, "
                    "updated_at=excluded.updated_at",
                    [(e["category"], e["key"],
                      json.dumps(e["value"], ensure_ascii=False),
                      e.get("source", "seed"), now)
                     for e in entries],
                )
            return {"count": len(entries), "status": "bulk_upserted"}
        finally:
            conn.close()

    def categories(self):
        """List all knowledge categories with entry counts."""
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT category, COUNT(*) FROM travel_knowledge GROUP BY category ORDER BY category",
            ).fetchall()
            return {"categories": [{"name": r[0], "count": r[1]} for r in rows]}
        finally:
            conn.close()

    def delete(self, category, key):
        conn = get_connection(self.db_path)
        try:
            with conn:
                result = conn.execute(
                    "DELETE FROM travel_knowledge WHERE category=? AND key=?",
                    (category, key),
                )
            return {"deleted": result.rowcount}
        finally:
            conn.close()