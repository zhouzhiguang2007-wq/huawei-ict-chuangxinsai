"""Module D: Guided questionnaire store.

Proactive user prompting templates that the orchestrator reads step-by-step
to guide users into providing detailed trip information.  Each step maps to
a dimension (destination, budget, accommodation, photo needs, etc.) and
targets one or more skills, ensuring all 9 skills get used.
"""

import json
from datetime import datetime, timezone
from .db import get_connection


class QuestionnaireStore:

    def __init__(self, db_path=None):
        self.db_path = db_path

    def get_step(self, step):
        """Get a single questionnaire step by number."""
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT step, dimension, question, question_type, options_json, "
                "allow_custom, triggers_skill, tip, is_optional, updated_at "
                "FROM guided_questions WHERE step=?",
                (step,),
            ).fetchone()
            if not row:
                return {"found": False}
            return {"found": True, "step": row[0], "dimension": row[1],
                    "question": row[2], "question_type": row[3],
                    "options": json.loads(row[4]) if row[4] else [],
                    "allow_custom": bool(row[5]),
                    "triggers_skill": row[6], "tip": row[7],
                    "is_optional": bool(row[8]), "updated_at": row[9]}
        finally:
            conn.close()

    def list_all(self):
        """List all questionnaire steps in order."""
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT step, dimension, question, question_type, options_json, "
                "allow_custom, triggers_skill, tip, is_optional "
                "FROM guided_questions ORDER BY step",
            ).fetchall()
            steps = []
            for r in rows:
                steps.append({
                    "step": r[0], "dimension": r[1], "question": r[2],
                    "question_type": r[3],
                    "options": json.loads(r[4]) if r[4] else [],
                    "allow_custom": bool(r[5]),
                    "triggers_skill": r[6], "tip": r[7],
                    "is_optional": bool(r[8]),
                })
            return {"steps": steps, "count": len(steps)}
        finally:
            conn.close()

    def get_by_dimension(self, dimension):
        """Get questionnaire step(s) for a specific dimension."""
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT step, dimension, question, question_type, options_json, "
                "allow_custom, triggers_skill, tip, is_optional "
                "FROM guided_questions WHERE dimension=? ORDER BY step",
                (dimension,),
            ).fetchall()
            steps = []
            for r in rows:
                steps.append({
                    "step": r[0], "dimension": r[1], "question": r[2],
                    "question_type": r[3],
                    "options": json.loads(r[4]) if r[4] else [],
                    "allow_custom": bool(r[5]),
                    "triggers_skill": r[6], "tip": r[7],
                    "is_optional": bool(r[8]),
                })
            return {"dimension": dimension, "steps": steps,
                    "count": len(steps)}
        finally:
            conn.close()

    def list_dimensions(self):
        """List all questionnaire dimensions in order."""
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT DISTINCT dimension FROM guided_questions ORDER BY step",
            ).fetchall()
            return {"dimensions": [r[0] for r in rows]}
        finally:
            conn.close()

    def upsert(self, step, dimension, question, question_type,
               options=None, allow_custom=True, triggers_skill="",
               tip=None, is_optional=False):
        """Insert or update a questionnaire step."""
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO guided_questions "
                    "(step, dimension, question, question_type, options_json, "
                    "allow_custom, triggers_skill, tip, is_optional, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(step) DO UPDATE SET "
                    "dimension=excluded.dimension, question=excluded.question, "
                    "question_type=excluded.question_type, "
                    "options_json=excluded.options_json, "
                    "allow_custom=excluded.allow_custom, "
                    "triggers_skill=excluded.triggers_skill, "
                    "tip=excluded.tip, is_optional=excluded.is_optional, "
                    "updated_at=excluded.updated_at",
                    (step, dimension, question, question_type,
                     json.dumps(options or [], ensure_ascii=False),
                     1 if allow_custom else 0,
                     triggers_skill, tip,
                     1 if is_optional else 0, now),
                )
            return {"step": step, "status": "upserted"}
        finally:
            conn.close()

    def bulk_upsert(self, entries):
        """Batch insert/update questionnaire steps."""
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.executemany(
                    "INSERT INTO guided_questions "
                    "(step, dimension, question, question_type, options_json, "
                    "allow_custom, triggers_skill, tip, is_optional, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(step) DO UPDATE SET "
                    "dimension=excluded.dimension, question=excluded.question, "
                    "question_type=excluded.question_type, "
                    "options_json=excluded.options_json, "
                    "allow_custom=excluded.allow_custom, "
                    "triggers_skill=excluded.triggers_skill, "
                    "tip=excluded.tip, is_optional=excluded.is_optional, "
                    "updated_at=excluded.updated_at",
                    [(e["step"], e["dimension"], e["question"], e["question_type"],
                      json.dumps(e.get("options", []), ensure_ascii=False),
                      1 if e.get("allow_custom", True) else 0,
                      e.get("triggers_skill", ""),
                      e.get("tip"),
                      1 if e.get("is_optional", False) else 0, now)
                     for e in entries],
                )
            return {"count": len(entries), "status": "bulk_upserted"}
        finally:
            conn.close()

    def next_step(self, current_step):
        """Get the next questionnaire step after the current one."""
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT step, dimension, question, question_type, options_json, "
                "allow_custom, triggers_skill, tip, is_optional "
                "FROM guided_questions WHERE step > ? ORDER BY step LIMIT 1",
                (current_step,),
            ).fetchone()
            if not row:
                return {"found": False}
            return {"found": True, "step": row[0], "dimension": row[1],
                    "question": row[2], "question_type": row[3],
                    "options": json.loads(row[4]) if row[4] else [],
                    "allow_custom": bool(row[5]),
                    "triggers_skill": row[6], "tip": row[7],
                    "is_optional": bool(row[8])}
        finally:
            conn.close()