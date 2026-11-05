"""One tool interface for local skills and hosted agents; no model or network I/O.

Extended with internal private database actions:
  - knowledge_query: query travel domain knowledge (Module A)
  - knowledge_upsert: add/update knowledge entries (Module A)
  - session_put: store interaction context / intermediate results (Module B)
  - session_get: retrieve context for a trip (Module B)
  - session_clear: delete context for a trip or stage (Module B)
  - registry_query: match skills by query / list all skills (Module C)
  - registry_get: get full metadata for one skill (Module C)
  - questionnaire_get_step: get a guided question by step number (Module D)
  - questionnaire_list: list all guided questions in order (Module D)
  - questionnaire_next: get the next question after current step (Module D)
  - seed: populate the internal database with pre-filled data
"""

import importlib.util
import json
import os
import sqlite3
from copy import deepcopy
from pathlib import Path

from .contracts import (VERSION, SKILLS, KNOWLEDGE_CATEGORIES, REGISTRY_CATEGORIES,
                        QUESTIONNAIRE_DIMENSIONS, QUESTION_TYPES,
                        adapt_requirements, merge_preferences,
                        nonempty, object_value, validate_preferences)
from .preferences import PreferenceStore
from .knowledge import KnowledgeStore
from .session import SessionStore
from .registry import SkillRegistry
from .questionnaire import QuestionnaireStore


DEFAULT_DB = Path(os.environ.get("TRAVEL_PREFERENCES_DB", "~/.travel-planner/preferences.sqlite3")).expanduser()
DEFAULT_INTERNAL_DB = Path(os.environ.get("TRAVEL_INTERNAL_DB", "~/.travel-planner/internal.sqlite3")).expanduser()


class TravelTools:
    """Construct once in a trusted host; user_id is never extracted from model text."""

    def __init__(self, db_path=DEFAULT_DB, internal_db_path=None):
        self.store = PreferenceStore(db_path)
        self.internal_db = internal_db_path or DEFAULT_INTERNAL_DB
        self.knowledge = KnowledgeStore(self.internal_db)
        self.session = SessionStore(self.internal_db)
        self.registry = SkillRegistry(self.internal_db)
        self.questionnaire = QuestionnaireStore(self.internal_db)

    def handle(self, request, *, user_id):
        action = request.get("action") if isinstance(request, dict) else None
        try:
            nonempty(user_id, "trusted user_id")
            object_value(request, "request")
            allowed = {
                # preference actions
                "get": {"action"},
                "update": {"action", "preferences", "confirmed", "source"},
                "delete": {"action", "fields"},
                "clear": {"action"},
                "prepare": {"action", "context"},
                "invoke": {"action", "context"},
                # knowledge actions (Module A)
                "knowledge_query": {"action", "category", "key", "keyword"},
                "knowledge_upsert": {"action", "category", "key", "value", "source"},
                "knowledge_categories": {"action"},
                # session actions (Module B)
                "session_put": {"action", "trip_id", "skill", "stage", "key", "value"},
                "session_get": {"action", "trip_id", "skill", "stage", "key"},
                "session_get_requirements": {"action", "trip_id"},
                "session_list_trips": {"action"},
                "session_clear_trip": {"action", "trip_id"},
                "session_clear_stage": {"action", "trip_id", "skill", "stage"},
                # registry actions (Module C)
                "registry_query": {"action", "query"},
                "registry_get": {"action", "skill_name"},
                "registry_list": {"action"},
                "registry_dependencies": {"action", "skill_name"},
                # questionnaire actions (Module D)
                "questionnaire_get_step": {"action", "step"},
                "questionnaire_list": {"action"},
                "questionnaire_next": {"action", "current_step"},
                "questionnaire_dimensions": {"action"},
                # seed action
                "seed": {"action"},
            }
            if not isinstance(action, str) or action not in allowed:
                raise ValueError("unsupported action")
            if request.keys() - allowed[action]:
                raise ValueError("unexpected request fields (identity is supplied by the host)")

            # --- preference actions ---
            if action == "get":
                data = self.store.get(user_id)
            elif action == "update":
                data = self.store.update(user_id, request.get("preferences"),
                                         request.get("confirmed"), request.get("source"))
            elif action == "delete":
                if "fields" not in request or request["fields"] is None:
                    raise ValueError("delete requires fields; use clear to delete all")
                data = self.store.delete(user_id, request["fields"])
            elif action == "clear":
                data = self.store.delete(user_id)
            elif action in ("prepare", "invoke"):
                data, warnings = self._prepare(request.get("context"), user_id)
                if action == "invoke":
                    data["result"] = self._invoke(data["context"])
                return self._result(action, "ok", data, warnings)

            # --- knowledge actions (Module A) ---
            elif action == "knowledge_query":
                data = self.knowledge.query(
                    category=request.get("category"),
                    key=request.get("key"),
                    keyword=request.get("keyword"),
                )
            elif action == "knowledge_upsert":
                cat = request.get("category")
                if cat not in KNOWLEDGE_CATEGORIES:
                    raise ValueError("unsupported knowledge category: " + str(cat))
                nonempty(request.get("key"), "key")
                data = self.knowledge.upsert(
                    cat, request["key"], request["value"],
                    request.get("source", "user"),
                )
            elif action == "knowledge_categories":
                data = self.knowledge.categories()

            # --- session actions (Module B) ---
            elif action == "session_put":
                nonempty(request.get("trip_id"), "trip_id")
                if request.get("skill") not in SKILLS:
                    raise ValueError("unsupported skill")
                nonempty(request.get("stage"), "stage")
                nonempty(request.get("key"), "key")
                data = self.session.put(
                    request["trip_id"], request["skill"],
                    request["stage"], request["key"], request["value"],
                )
            elif action == "session_get":
                nonempty(request.get("trip_id"), "trip_id")
                data = self.session.get(
                    request["trip_id"],
                    skill=request.get("skill"),
                    stage=request.get("stage"),
                    key=request.get("key"),
                )
            elif action == "session_get_requirements":
                nonempty(request.get("trip_id"), "trip_id")
                data = self.session.get_requirements(request["trip_id"])
            elif action == "session_list_trips":
                data = self.session.list_trips()
            elif action == "session_clear_trip":
                nonempty(request.get("trip_id"), "trip_id")
                data = self.session.clear_trip(request["trip_id"])
            elif action == "session_clear_stage":
                nonempty(request.get("trip_id"), "trip_id")
                if request.get("skill") not in SKILLS:
                    raise ValueError("unsupported skill")
                nonempty(request.get("stage"), "stage")
                data = self.session.clear_stage(
                    request["trip_id"], request["skill"], request["stage"],
                )

            # --- registry actions (Module C) ---
            elif action == "registry_query":
                nonempty(request.get("query"), "query")
                data = self.registry.match(request["query"])
            elif action == "registry_get":
                nonempty(request.get("skill_name"), "skill_name")
                data = self.registry.get(request["skill_name"])
            elif action == "registry_list":
                data = self.registry.list_all()
            elif action == "registry_dependencies":
                nonempty(request.get("skill_name"), "skill_name")
                data = self.registry.dependencies(request["skill_name"])

            # --- questionnaire actions (Module D) ---
            elif action == "questionnaire_get_step":
                step = request.get("step")
                if not isinstance(step, int) or step < 1:
                    raise ValueError("step must be a positive integer")
                data = self.questionnaire.get_step(step)
            elif action == "questionnaire_list":
                data = self.questionnaire.list_all()
            elif action == "questionnaire_next":
                current = request.get("current_step")
                if not isinstance(current, int) or current < 0:
                    raise ValueError("current_step must be a nonnegative integer")
                data = self.questionnaire.next_step(current)
            elif action == "questionnaire_dimensions":
                data = self.questionnaire.list_dimensions()

            # --- seed action ---
            elif action == "seed":
                from .seed_knowledge import seed_all
                data = seed_all(self.internal_db)

            return self._result(action, "ok", data)
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
            return self._result(action, "invalid", errors=[str(exc)])
        except (OSError, sqlite3.Error):
            return self._result(action, "unavailable", errors=["工具或存储不可用；未确认保存成功。"])

    @staticmethod
    def _result(action, status, data=None, warnings=None, errors=None):
        return {"schema_version": VERSION, "action": action, "status": status,
                "data": data if data is not None else {},
                "warnings": warnings or [], "errors": errors or []}

    def _prepare(self, context, user_id):
        object_value(context, "context")
        if context.get("schema_version") != VERSION:
            raise ValueError("unsupported context schema_version")
        if context.get("skill") not in SKILLS:
            raise ValueError("unsupported skill")
        nonempty(context.get("trip_id"), "trip_id")
        allowed = {"schema_version", "skill", "trip_id", "requirements", "trip_preferences",
                   "explicit_preference_fields", "payload", "preference_snapshot"}
        if context.keys() - allowed:
            raise ValueError("unexpected context fields")
        prepared = deepcopy(context)
        requirements = prepared.setdefault("requirements", {})
        object_value(requirements, "requirements")
        current = requirements.get("preferences")
        current = {} if current is None else current
        trip = prepared.get("trip_preferences", {})
        validate_preferences(current)
        validate_preferences(trip)
        for field in ("destination", "dates", "travelers", "budget"):
            if requirements.get(field) is not None:
                object_value(requirements[field], "requirements." + field)
        object_value(prepared.setdefault("payload", {}), "payload")
        warnings = []
        snapshot = prepared.get("preference_snapshot")
        if snapshot is None:
            try:
                saved = self.store.get(user_id)["preferences"]
                memory_status = "loaded"
            except (OSError, sqlite3.Error):
                saved = {}
                memory_status = "unavailable"
                warnings.append("偏好读取失败；使用本次需求继续，缺项正常追问。")
            saved, origins = merge_preferences(saved, trip, current,
                                               prepared.get("explicit_preference_fields", []))
            snapshot = {"preferences": saved, "origins": origins, "memory_status": memory_status}
        else:
            object_value(snapshot, "preference_snapshot")
            validate_preferences(snapshot.get("preferences"))
            if current and current != snapshot["preferences"]:
                raise ValueError("preferences changed; discard snapshot and prepare a new orchestration run")
            if snapshot.get("memory_status") not in {"loaded", "unavailable"}:
                raise ValueError("invalid snapshot memory_status")
            object_value(snapshot.get("origins"), "snapshot origins")
            if set(snapshot["origins"]) != set(snapshot["preferences"]) or any(
                    v not in {"memory", "trip", "current"} for v in snapshot["origins"].values()):
                raise ValueError("invalid snapshot origins")
        # A snapshot is host-owned and reused unchanged across one orchestration run.
        requirements["preferences"] = deepcopy(snapshot["preferences"])
        prepared["preference_snapshot"] = deepcopy(snapshot)
        prepared.pop("trip_preferences", None)
        prepared.pop("explicit_preference_fields", None)
        mapping = adapt_requirements(prepared["skill"], requirements)
        warnings.extend(mapping.pop("warnings"))
        return {"context": prepared, **mapping}, warnings

    @staticmethod
    def _invoke(context):
        # Only deterministic operations; payload retains each module's native schema.
        targets = {
            "travel-requirement-analysis": ("validate_requirements.py", "validate_requirements"),
            "multi-platform-travel-planner": ("validate_route_timeline.py", "validate_route"),
            "travel-accommodation-advisor": ("compare_stay_costs.py", "compare"),
            "travel-plan-review": ("validate_itinerary.py", "review"),
            "travel-time-pocket": ("evaluate_time_pocket.py", "evaluate_time_pocket"),
        }
        skill = context["skill"]
        if skill not in targets:
            raise ValueError("this skill uses prepare plus its documented workflow/CLI; invoke is unsupported")
        filename, function = targets[skill]
        path = Path(__file__).resolve().parents[1] / "skills" / skill / "scripts" / filename
        spec = importlib.util.spec_from_file_location("travel_shared_" + skill.replace("-", "_"), path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        payload = deepcopy(context["payload"])
        if skill == "travel-requirement-analysis":
            payload = deepcopy(context["requirements"])
        if skill == "travel-plan-review":
            # Canonical hard requirements must actually reach the validator.
            for key in ("plan", "candidate"):
                if isinstance(payload.get(key), dict):
                    payload[key].setdefault("requirements", {}).update(
                        adapt_requirements(skill, context["requirements"])["input_hints"])
            if "as_of" not in payload:
                from datetime import datetime, timezone
                payload["as_of"] = datetime.now(timezone.utc).isoformat()
        return getattr(module, function)(payload)


def main(args, *, user_id, db_path=DEFAULT_DB):
    """Trusted AgentArts backend bridge: input request_json, output result_json/status."""
    tools = TravelTools(db_path)
    try:
        request = json.loads(args["request_json"])
    except (KeyError, TypeError, ValueError):
        result = tools._result(None, "invalid", errors=["request_json must contain JSON"])
    else:
        result = tools.handle(request, user_id=user_id)
    return {"status": result["status"], "result_json": json.dumps(result, ensure_ascii=False)}
