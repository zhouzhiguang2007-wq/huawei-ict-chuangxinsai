"""One tool interface for local skills and hosted agents; no model or network I/O."""

import importlib.util
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from .contracts import (VERSION, SKILLS, adapt_requirements, merge_preferences,
                        nonempty, object_value, validate_preferences)
from .preferences import PreferenceStore


DEFAULT_DB = Path(os.environ.get("TRAVEL_PREFERENCES_DB", "~/.travel-planner/preferences.sqlite3")).expanduser()


class TravelTools:
    """Construct once in a trusted host; user_id is never extracted from model text."""

    def __init__(self, db_path=DEFAULT_DB, *, snapshot_secret=None, clock=None):
        self.store = PreferenceStore(db_path)
        secret = snapshot_secret if snapshot_secret is not None else os.environ.get("TRAVEL_SNAPSHOT_SECRET")
        if secret is None:
            secret = secrets.token_bytes(32)
        elif isinstance(secret, str):
            secret = secret.encode("utf-8")
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("snapshot secret must contain at least 32 bytes")
        self._snapshot_secret = secret
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _snapshot_seal(self, snapshot, user_id, trip_id):
        canonical = {"schema_version": VERSION, "user_id": user_id, "trip_id": trip_id,
                     "preferences": snapshot["preferences"], "origins": snapshot["origins"],
                     "memory_status": snapshot["memory_status"]}
        message = json.dumps(canonical, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")
        return hmac.new(self._snapshot_secret, message, hashlib.sha256).hexdigest()

    def handle(self, request, *, user_id):
        action = request.get("action") if isinstance(request, dict) else None
        try:
            nonempty(user_id, "trusted user_id")
            object_value(request, "request")
            allowed = {
                "get": {"action"},
                "update": {"action", "preferences", "confirmed", "source"},
                "delete": {"action", "fields"},
                "clear": {"action"},
                "prepare": {"action", "context"},
                "invoke": {"action", "context"},
            }
            if not isinstance(action, str) or action not in allowed:
                raise ValueError("unsupported action")
            if request.keys() - allowed[action]:
                raise ValueError("unexpected request fields (identity is supplied by the host)")
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
            else:
                data, warnings = self._prepare(request.get("context"), user_id)
                if action == "invoke":
                    data["result"] = self._invoke(data["context"])
                return self._result(action, "ok", data, warnings)
            return self._result(action, "ok", data)
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
            return self._result(action, "invalid", errors=[str(exc)])
        except (OSError, sqlite3.Error):
            return self._result(action, "unavailable", errors=["工具或偏好存储不可用；未确认保存成功。"])

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
            snapshot["seal"] = self._snapshot_seal(snapshot, user_id, prepared["trip_id"])
        else:
            object_value(snapshot, "preference_snapshot")
            if "trip_preferences" in prepared or "explicit_preference_fields" in prepared:
                raise ValueError("discard snapshot before changing trip preferences")
            validate_preferences(snapshot.get("preferences"))
            if current and current != snapshot["preferences"]:
                raise ValueError("preferences changed; discard snapshot and prepare a new orchestration run")
            if snapshot.get("memory_status") not in {"loaded", "unavailable"}:
                raise ValueError("invalid snapshot memory_status")
            object_value(snapshot.get("origins"), "snapshot origins")
            if set(snapshot["origins"]) != set(snapshot["preferences"]) or any(
                    v not in {"memory", "trip", "current"} for v in snapshot["origins"].values()):
                raise ValueError("invalid snapshot origins")
            if set(snapshot) != {"preferences", "origins", "memory_status", "seal"}:
                raise ValueError("invalid snapshot fields")
            if (not isinstance(snapshot["seal"], str) or not hmac.compare_digest(
                    snapshot["seal"], self._snapshot_seal(snapshot, user_id, prepared["trip_id"]))):
                raise ValueError("snapshot does not belong to this user and trip or was changed")
        # A snapshot is host-owned and reused unchanged across one orchestration run.
        requirements["preferences"] = deepcopy(snapshot["preferences"])
        prepared["preference_snapshot"] = deepcopy(snapshot)
        prepared.pop("trip_preferences", None)
        prepared.pop("explicit_preference_fields", None)
        mapping = adapt_requirements(prepared["skill"], requirements)
        warnings.extend(mapping.pop("warnings"))
        return {"context": prepared, **mapping}, warnings

    def _invoke(self, context):
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
            # The model-facing payload cannot move the check clock into the past.
            checked_at = self._clock()
            if not isinstance(checked_at, datetime) or checked_at.utcoffset() is None:
                raise ValueError("trusted clock must return an aware datetime")
            payload["as_of"] = checked_at.isoformat()
        return getattr(module, function)(payload)


def main(args, *, user_id, db_path=DEFAULT_DB, allow_memory_write=False):
    """Backend bridge; writes require a separate trusted host decision."""
    tools = TravelTools(db_path)
    try:
        request = json.loads(args["request_json"])
    except (KeyError, TypeError, ValueError):
        result = tools._result(None, "invalid", errors=["request_json must contain JSON"])
    else:
        if (isinstance(request, dict) and request.get("action") in {"update", "delete", "clear"}
                and allow_memory_write is not True):
            result = tools._result(request.get("action"), "invalid",
                                   errors=["memory changes require trusted host authorization"])
        else:
            result = tools.handle(request, user_id=user_id)
    return {"status": result["status"], "result_json": json.dumps(result, ensure_ascii=False)}
