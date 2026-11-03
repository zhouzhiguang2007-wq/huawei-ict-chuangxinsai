"""Module C: Skill capability registry.

Detailed metadata about each skill in the plugin: trigger keywords,
dependencies, output format, category.  The orchestrator (or the host
agent) queries this table to discover which skills are relevant for a
given user request, instead of relying solely on RAG title matching.
"""

import json
from datetime import datetime, timezone
from .db import get_connection


class SkillRegistry:

    def __init__(self, db_path=None):
        self.db_path = db_path

    def get(self, skill_name):
        """Get full metadata for a specific skill."""
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT skill_name, display_name, category, trigger_keywords, "
                "description, dependencies, output_summary, updated_at "
                "FROM skill_registry WHERE skill_name=?",
                (skill_name,),
            ).fetchone()
            if not row:
                return {"found": False}
            return {"found": True, "skill_name": row[0],
                    "display_name": row[1], "category": row[2],
                    "trigger_keywords": json.loads(row[3]),
                    "description": row[4],
                    "dependencies": json.loads(row[5]) if row[5] else [],
                    "output_summary": row[6], "updated_at": row[7]}
        finally:
            conn.close()

    def list_all(self):
        """List all registered skills with their metadata."""
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT skill_name, display_name, category, trigger_keywords, "
                "description, dependencies, output_summary, updated_at "
                "FROM skill_registry ORDER BY category, skill_name",
            ).fetchall()
            skills = []
            for r in rows:
                skills.append({
                    "skill_name": r[0], "display_name": r[1], "category": r[2],
                    "trigger_keywords": json.loads(r[3]),
                    "description": r[4],
                    "dependencies": json.loads(r[5]) if r[5] else [],
                    "output_summary": r[6], "updated_at": r[7],
                })
            return {"skills": skills, "count": len(skills)}
        finally:
            conn.close()

    def match(self, query):
        """Find skills whose trigger keywords or description match the query.

        Returns skills sorted by number of keyword matches (descending).
        """
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT skill_name, display_name, category, trigger_keywords, "
                "description, dependencies, output_summary "
                "FROM skill_registry",
            ).fetchall()
            query_lower = query.lower()
            scored = []
            for r in rows:
                keywords = json.loads(r[3])
                match_count = sum(1 for kw in keywords if kw.lower() in query_lower)
                desc_match = 1 if query_lower in r[4].lower() else 0
                total = match_count + desc_match
                if total > 0:
                    scored.append((total, {
                        "skill_name": r[0], "display_name": r[1],
                        "category": r[2], "trigger_keywords": keywords,
                        "description": r[4],
                        "dependencies": json.loads(r[5]) if r[5] else [],
                        "output_summary": r[6],
                        "match_score": total,
                    }))
            scored.sort(key=lambda x: -x[0])
            return {"query": query,
                    "matched_skills": [s for _, s in scored],
                    "count": len(scored)}
        finally:
            conn.close()

    def upsert(self, skill_name, display_name, category, trigger_keywords,
               description, dependencies=None, output_summary=None):
        """Insert or update a skill registry entry."""
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO skill_registry "
                    "(skill_name, display_name, category, trigger_keywords, "
                    "description, dependencies, output_summary, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(skill_name) DO UPDATE SET "
                    "display_name=excluded.display_name, category=excluded.category, "
                    "trigger_keywords=excluded.trigger_keywords, "
                    "description=excluded.description, "
                    "dependencies=excluded.dependencies, "
                    "output_summary=excluded.output_summary, "
                    "updated_at=excluded.updated_at",
                    (skill_name, display_name, category,
                     json.dumps(trigger_keywords, ensure_ascii=False),
                     description,
                     json.dumps(dependencies or [], ensure_ascii=False),
                     output_summary, now),
                )
            return {"skill_name": skill_name, "status": "upserted"}
        finally:
            conn.close()

    def bulk_upsert(self, entries):
        """Batch insert/update skill registry entries."""
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.executemany(
                    "INSERT INTO skill_registry "
                    "(skill_name, display_name, category, trigger_keywords, "
                    "description, dependencies, output_summary, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(skill_name) DO UPDATE SET "
                    "display_name=excluded.display_name, category=excluded.category, "
                    "trigger_keywords=excluded.trigger_keywords, "
                    "description=excluded.description, "
                    "dependencies=excluded.dependencies, "
                    "output_summary=excluded.output_summary, "
                    "updated_at=excluded.updated_at",
                    [(e["skill_name"], e["display_name"], e["category"],
                      json.dumps(e["trigger_keywords"], ensure_ascii=False),
                      e["description"],
                      json.dumps(e.get("dependencies", []), ensure_ascii=False),
                      e.get("output_summary"), now)
                     for e in entries],
                )
            return {"count": len(entries), "status": "bulk_upserted"}
        finally:
            conn.close()

    def dependencies(self, skill_name):
        """Get the dependency chain for a skill (transitive)."""
        visited = set()
        chain = []
        conn = get_connection(self.db_path)
        try:
            def _walk(name):
                if name in visited:
                    return
                visited.add(name)
                row = conn.execute(
                    "SELECT dependencies FROM skill_registry WHERE skill_name=?",
                    (name,),
                ).fetchone()
                if not row:
                    return
                deps = json.loads(row[0]) if row[0] else []
                for dep in deps:
                    _walk(dep)
                    if dep not in chain:
                        chain.append(dep)
            _walk(skill_name)
            return {"skill_name": skill_name,
                    "dependency_chain": chain}
        finally:
            conn.close()