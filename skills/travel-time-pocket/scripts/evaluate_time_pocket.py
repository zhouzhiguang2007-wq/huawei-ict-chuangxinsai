#!/usr/bin/env python3
"""Deterministically evaluate whether pocket-trip candidates fit a time window."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _parse_datetime(value: Any, field: str, errors: List[str]) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        errors.append("%s must be an ISO 8601 string" % field)
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append("%s must be an ISO 8601 datetime" % field)
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        errors.append("%s must include a UTC offset" % field)
        return None
    return parsed


def _optional_datetime(value: Any, field: str, errors: List[str]) -> Optional[datetime]:
    return None if value in (None, "") else _parse_datetime(value, field, errors)


def _minutes(value: Any, field: str, errors: List[str], positive: bool = False) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append("%s must be an integer" % field)
        return None
    if value < 0 or (positive and value == 0):
        errors.append("%s must be %s" % (field, "positive" if positive else "non-negative"))
        return None
    return value


def _route(
    candidate: Dict[str, Any],
    nested_field: str,
    legacy_field: str,
    route_policy: Dict[str, Any],
    current: datetime,
    distinct_places: bool,
    errors: List[str],
) -> Dict[str, Any]:
    """Normalize a 1.1 route object while continuing to accept 1.0 minute fields."""
    value = candidate.get(nested_field)
    if value is None:
        duration = _minutes(candidate.get(legacy_field), legacy_field, errors)
        issues: List[str] = []
        if route_policy["require_status"]:
            issues.append("route_status_missing")
        if route_policy["require_queried_at"]:
            issues.append("route_query_time_missing")
        return {
            "duration_minutes": duration,
            "availability": "available" if duration is not None else "unknown",
            "queried_at": None,
            "quality": "legacy",
            "issues": issues,
            "warnings": ["%s uses legacy duration without route status or query time" % nested_field],
        }
    if not isinstance(value, dict):
        errors.append("%s must be an object" % nested_field)
        return {"duration_minutes": None, "availability": "unknown", "issues": [], "warnings": []}

    duration_value = value.get("duration_minutes")
    duration = None if duration_value is None else _minutes(duration_value, "%s.duration_minutes" % nested_field, errors)
    availability = value.get("availability", "unknown")
    if availability not in ("available", "unavailable", "unknown"):
        errors.append("%s.availability must be available, unavailable, or unknown" % nested_field)
        availability = "unknown"
    queried_at = _optional_datetime(value.get("queried_at"), "%s.queried_at" % nested_field, errors)
    issues: List[str] = []

    if availability == "available" and duration is None:
        errors.append("%s.duration_minutes is required when route is available" % nested_field)
    if availability == "unavailable":
        issues.append("route_unavailable")
    elif availability == "unknown":
        issues.append("route_unknown")

    if route_policy["require_queried_at"] and queried_at is None:
        issues.append("route_query_time_missing")
    elif queried_at is not None:
        age_minutes = (current - queried_at).total_seconds() / 60
        if age_minutes < -5:
            errors.append("%s.queried_at must not be in the future" % nested_field)
        elif age_minutes > route_policy["max_age_minutes"]:
            issues.append("route_data_stale")

    if availability == "available" and duration == 0 and distinct_places:
        issues.append("route_zero_duration_between_distinct_places")

    return {
        "duration_minutes": duration,
        "availability": availability,
        "queried_at": queried_at.isoformat() if queried_at else None,
        "quality": "verified" if not issues else "unverified",
        "issues": issues,
        "warnings": [],
    }


def _reason_text(code: str, route_name: str = "route") -> str:
    messages = {
        "route_unavailable": "%s is confirmed unavailable" % route_name,
        "route_unknown": "%s availability is unknown" % route_name,
        "route_status_missing": "%s status is missing" % route_name,
        "route_query_time_missing": "%s query time is missing" % route_name,
        "route_data_stale": "%s data is stale" % route_name,
        "route_zero_duration_between_distinct_places": "%s has zero duration between distinct places" % route_name,
    }
    return messages.get(code, code)


def _opening_slot(
    candidate: Dict[str, Any],
    ready_at: datetime,
    visit_minutes: int,
    latest_entry: Optional[datetime],
    errors: List[str],
) -> Tuple[Optional[datetime], bool, int]:
    if candidate.get("always_open") is True:
        if latest_entry is not None and ready_at > latest_entry:
            return None, True, 0
        return ready_at, True, 0

    windows = candidate.get("opening_windows")
    if not isinstance(windows, list) or not windows:
        return ready_at, False, 0

    valid_windows: List[Tuple[datetime, datetime]] = []
    for index, window in enumerate(windows):
        if not isinstance(window, dict):
            errors.append("opening_windows[%d] must be an object" % index)
            continue
        start = _parse_datetime(window.get("start"), "opening_windows[%d].start" % index, errors)
        end = _parse_datetime(window.get("end"), "opening_windows[%d].end" % index, errors)
        if start and end:
            if end <= start:
                errors.append("opening_windows[%d] end must be after start" % index)
            else:
                valid_windows.append((start, end))

    for window_start, window_end in sorted(valid_windows, key=lambda item: item[0]):
        activity_start = max(ready_at, window_start)
        if latest_entry is not None and activity_start > latest_entry:
            continue
        if activity_start + timedelta(minutes=visit_minutes) <= window_end:
            wait = int((activity_start - ready_at).total_seconds() // 60)
            return activity_start, True, wait
    return None, True, 0


def _evaluate_candidate(
    candidate: Any,
    current: datetime,
    deadline: datetime,
    departure: datetime,
    buffer_minutes: int,
    route_policy: Dict[str, Any],
    origin_place_id: Optional[str],
    return_place_id: Optional[str],
    index: int,
) -> Dict[str, Any]:
    errors: List[str] = []
    if not isinstance(candidate, dict):
        return {"id": "candidate-%d" % index, "name": "", "status": "invalid", "reason_codes": ["invalid_candidate"], "reasons": ["candidate must be an object"]}

    candidate_id = str(candidate.get("id") or "candidate-%d" % index)
    name = str(candidate.get("name") or "")
    place_id = candidate.get("place_id")
    distinct_outbound = bool(origin_place_id and place_id and origin_place_id != place_id)
    distinct_return = bool(return_place_id and place_id and return_place_id != place_id)
    outbound_route = _route(candidate, "outbound_route", "travel_to_minutes", route_policy, current, distinct_outbound, errors)
    return_route = _route(candidate, "return_route", "travel_back_minutes", route_policy, current, distinct_return, errors)
    queue = _minutes(candidate.get("queue_minutes", 0), "queue_minutes", errors)
    visit = _minutes(candidate.get("minimum_visit_minutes"), "minimum_visit_minutes", errors, positive=True)
    latest_entry = _optional_datetime(candidate.get("latest_entry"), "latest_entry", errors)
    available = candidate.get("available")
    if available not in (True, False, None):
        errors.append("available must be true, false, or null")

    warnings = outbound_route.get("warnings", []) + return_route.get("warnings", [])
    result: Dict[str, Any] = {
        "id": candidate_id,
        "name": name,
        "status": "invalid",
        "reason_codes": [],
        "reasons": errors,
        "warnings": warnings,
    }
    if errors or None in (queue, visit):
        result["reason_codes"] = ["invalid_input"]
        return result

    if available is False:
        result.update({"status": "infeasible", "reason_codes": ["candidate_unavailable"], "reasons": ["candidate is confirmed unavailable"]})
        return result

    route_issues = [("outbound route", code) for code in outbound_route.get("issues", [])]
    route_issues += [("return route", code) for code in return_route.get("issues", [])]
    unavailable = [(label, code) for label, code in route_issues if code == "route_unavailable"]
    if unavailable:
        result.update({
            "status": "infeasible",
            "reason_codes": [code for _, code in unavailable],
            "reasons": [_reason_text(code, label) for label, code in unavailable],
        })
        return result

    outbound = outbound_route.get("duration_minutes")
    inbound = return_route.get("duration_minutes")
    if outbound is None or inbound is None:
        reason_codes = [code for _, code in route_issues] or ["route_duration_missing"]
        result.update({
            "status": "incomplete",
            "reason_codes": reason_codes,
            "reasons": [_reason_text(code, label) for label, code in route_issues] or ["route duration is missing"],
        })
        return result

    arrival = departure + timedelta(minutes=outbound)
    ready_at = arrival + timedelta(minutes=queue)
    opening_errors: List[str] = []
    activity_start, opening_known, opening_wait = _opening_slot(candidate, ready_at, visit, latest_entry, opening_errors)
    if opening_errors:
        result.update({"status": "invalid", "reason_codes": ["invalid_opening_window"], "reasons": opening_errors})
        return result
    if activity_start is None:
        reason_code = "latest_entry_missed" if latest_entry is not None and ready_at > latest_entry else "opening_window_too_short"
        result.update({
            "status": "infeasible",
            "arrival_time": arrival.isoformat(),
            "reason_codes": [reason_code],
            "reasons": ["latest entry time is missed" if reason_code == "latest_entry_missed" else "minimum visit does not fit an opening window"],
        })
        return result

    activity_end = activity_start + timedelta(minutes=visit)
    return_time = activity_end + timedelta(minutes=inbound)
    safe_return = return_time + timedelta(minutes=buffer_minutes)
    spare = int((deadline - safe_return).total_seconds() // 60)
    reason_codes: List[str] = []
    reasons: List[str] = []

    if safe_return > deadline:
        status = "infeasible"
        reason_codes.append("return_deadline_missed")
        reasons.append("safe return time is later than must_return_by")
    else:
        if available is None:
            reason_codes.append("candidate_availability_unknown")
            reasons.append("candidate availability is unknown")
        if not opening_known:
            reason_codes.append("opening_information_unknown")
            reasons.append("opening information is unknown")
        for label, code in route_issues:
            if code != "route_unavailable":
                reason_codes.append(code)
                reasons.append(_reason_text(code, label))
        status = "incomplete" if reason_codes else "feasible"

    result.update(
        {
            "status": status,
            "departure_time": departure.isoformat(),
            "arrival_time": arrival.isoformat(),
            "activity_start_time": activity_start.isoformat(),
            "activity_end_time": activity_end.isoformat(),
            "return_time": return_time.isoformat(),
            "safe_return_time": safe_return.isoformat(),
            "spare_minutes": spare,
            "duration_breakdown": {
                "travel_to_minutes": outbound,
                "queue_minutes": queue,
                "opening_wait_minutes": opening_wait,
                "visit_minutes": visit,
                "travel_back_minutes": inbound,
                "buffer_minutes": buffer_minutes,
                "total_after_departure_minutes": int((safe_return - departure).total_seconds() // 60),
            },
            "route_checks": {"outbound": outbound_route, "return": return_route},
            "reason_codes": reason_codes,
            "reasons": reasons,
        }
    )
    return result


def evaluate_time_pocket(data: Any) -> Dict[str, Any]:
    errors: List[str] = []
    if not isinstance(data, dict):
        return {"status": "invalid", "window_minutes": None, "buffer_minutes": None, "candidates": [], "errors": ["root must be an object"]}

    current = _parse_datetime(data.get("current_time"), "current_time", errors)
    deadline = _parse_datetime(data.get("must_return_by"), "must_return_by", errors)
    buffer_minutes = _minutes(data.get("buffer_minutes"), "buffer_minutes", errors)
    preparation_minutes = _minutes(data.get("departure_preparation_minutes", 0), "departure_preparation_minutes", errors)
    schema_version = str(data.get("schema_version") or "1.0")
    strict_default = schema_version != "1.0"
    raw_policy = data.get("route_policy", {})
    if not isinstance(raw_policy, dict):
        errors.append("route_policy must be an object")
        raw_policy = {}
    require_queried_at = raw_policy.get("require_queried_at", strict_default)
    if not isinstance(require_queried_at, bool):
        errors.append("route_policy.require_queried_at must be boolean")
        require_queried_at = strict_default
    require_status = raw_policy.get("require_status", strict_default)
    if not isinstance(require_status, bool):
        errors.append("route_policy.require_status must be boolean")
        require_status = strict_default
    max_age_minutes = _minutes(raw_policy.get("max_age_minutes", 30), "route_policy.max_age_minutes", errors, positive=True)
    route_policy = {
        "require_status": require_status,
        "require_queried_at": require_queried_at,
        "max_age_minutes": max_age_minutes or 30,
    }
    candidates = data.get("candidates")
    if not isinstance(candidates, list):
        errors.append("candidates must be an array")
        candidates = []
    elif not candidates:
        errors.append("candidates must not be empty")

    if current and deadline and deadline <= current:
        errors.append("must_return_by must be after current_time")
    if errors or current is None or deadline is None or buffer_minutes is None or preparation_minutes is None:
        return {"status": "invalid", "window_minutes": None, "buffer_minutes": buffer_minutes, "candidates": [], "errors": errors}

    departure = current + timedelta(minutes=preparation_minutes)
    origin_place_id = data.get("origin_place_id")
    return_place_id = data.get("return_place_id")
    evaluated = [
        _evaluate_candidate(candidate, current, deadline, departure, buffer_minutes, route_policy, origin_place_id, return_place_id, index)
        for index, candidate in enumerate(candidates, start=1)
    ]
    statuses = {item["status"] for item in evaluated}
    if "feasible" in statuses:
        status = "feasible"
    elif "incomplete" in statuses:
        status = "incomplete"
    elif statuses == {"invalid"}:
        status = "invalid"
    else:
        status = "infeasible"

    return {
        "status": status,
        "schema_version": schema_version,
        "window_minutes": int((deadline - current).total_seconds() // 60),
        "usable_minutes": max(0, int((deadline - departure).total_seconds() // 60)),
        "departure_preparation_minutes": preparation_minutes,
        "buffer_minutes": buffer_minutes,
        "route_policy": route_policy,
        "candidates": evaluated,
        "errors": [],
    }


def main(args: Dict[str, Any]) -> Dict[str, str]:
    """AgentArts entry point: input pocket_json; output status and report_json."""
    raw = args.get("pocket_json", "") if isinstance(args, dict) else ""
    try:
        data = json.loads(raw)
        report = evaluate_time_pocket(data)
    except (TypeError, json.JSONDecodeError) as exc:
        report = {"status": "invalid", "window_minutes": None, "buffer_minutes": None, "candidates": [], "errors": [str(exc)]}
    return {"status": report["status"], "report_json": json.dumps(report, ensure_ascii=False, separators=(",", ":"))}


def _cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", help="JSON file; reads stdin when omitted")
    options = parser.parse_args()
    try:
        raw = Path(options.input).read_text(encoding="utf-8") if options.input else sys.stdin.read()
        report = evaluate_time_pocket(json.loads(raw))
    except (OSError, json.JSONDecodeError) as exc:
        report = {"status": "invalid", "window_minutes": None, "buffer_minutes": None, "candidates": [], "errors": [str(exc)]}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(_cli())


