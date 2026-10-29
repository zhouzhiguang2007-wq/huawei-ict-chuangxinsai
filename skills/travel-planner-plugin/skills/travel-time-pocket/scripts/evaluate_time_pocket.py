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


def _minutes(value: Any, field: str, errors: List[str], positive: bool = False) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append("%s must be an integer" % field)
        return None
    if value < 0 or (positive and value == 0):
        errors.append("%s must be %s" % (field, "positive" if positive else "non-negative"))
        return None
    return value


def _opening_slot(
    candidate: Dict[str, Any],
    ready_at: datetime,
    visit_minutes: int,
    errors: List[str],
) -> Tuple[Optional[datetime], bool]:
    if candidate.get("always_open") is True:
        return ready_at, True

    windows = candidate.get("opening_windows")
    if not isinstance(windows, list) or not windows:
        return ready_at, False

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
        if activity_start + timedelta(minutes=visit_minutes) <= window_end:
            return activity_start, True
    return None, True


def _evaluate_candidate(
    candidate: Any,
    current: datetime,
    deadline: datetime,
    buffer_minutes: int,
    index: int,
) -> Dict[str, Any]:
    errors: List[str] = []
    if not isinstance(candidate, dict):
        return {"id": "candidate-%d" % index, "name": "", "status": "invalid", "reasons": ["candidate must be an object"]}

    candidate_id = str(candidate.get("id") or "candidate-%d" % index)
    name = str(candidate.get("name") or "")
    outbound = _minutes(candidate.get("travel_to_minutes"), "travel_to_minutes", errors)
    queue = _minutes(candidate.get("queue_minutes", 0), "queue_minutes", errors)
    visit = _minutes(candidate.get("minimum_visit_minutes"), "minimum_visit_minutes", errors, positive=True)
    inbound = _minutes(candidate.get("travel_back_minutes"), "travel_back_minutes", errors)
    available = candidate.get("available")
    if available not in (True, False, None):
        errors.append("available must be true, false, or null")

    result: Dict[str, Any] = {"id": candidate_id, "name": name, "status": "invalid", "reasons": errors}
    if errors or None in (outbound, queue, visit, inbound):
        return result

    if available is False:
        result.update({"status": "infeasible", "reasons": ["candidate is confirmed unavailable"]})
        return result

    arrival = current + timedelta(minutes=outbound)
    ready_at = arrival + timedelta(minutes=queue)
    opening_errors: List[str] = []
    activity_start, opening_known = _opening_slot(candidate, ready_at, visit, opening_errors)
    if opening_errors:
        result.update({"status": "invalid", "reasons": opening_errors})
        return result
    if activity_start is None:
        result.update({"status": "infeasible", "arrival_time": arrival.isoformat(), "reasons": ["minimum visit does not fit an opening window"]})
        return result

    activity_end = activity_start + timedelta(minutes=visit)
    return_time = activity_end + timedelta(minutes=inbound)
    safe_return = return_time + timedelta(minutes=buffer_minutes)
    spare = int((deadline - safe_return).total_seconds() // 60)
    reasons: List[str] = []

    if safe_return > deadline:
        status = "infeasible"
        reasons.append("safe return time is later than must_return_by")
    elif available is None or not opening_known:
        status = "incomplete"
        if available is None:
            reasons.append("availability is unknown")
        if not opening_known:
            reasons.append("opening information is unknown")
    else:
        status = "feasible"

    result.update(
        {
            "status": status,
            "arrival_time": arrival.isoformat(),
            "activity_start_time": activity_start.isoformat(),
            "activity_end_time": activity_end.isoformat(),
            "return_time": return_time.isoformat(),
            "safe_return_time": safe_return.isoformat(),
            "spare_minutes": spare,
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
    candidates = data.get("candidates")
    if not isinstance(candidates, list):
        errors.append("candidates must be an array")
        candidates = []
    elif not candidates:
        errors.append("candidates must not be empty")

    if current and deadline and deadline <= current:
        errors.append("must_return_by must be after current_time")
    if errors or current is None or deadline is None or buffer_minutes is None:
        return {"status": "invalid", "window_minutes": None, "buffer_minutes": buffer_minutes, "candidates": [], "errors": errors}

    evaluated = [
        _evaluate_candidate(candidate, current, deadline, buffer_minutes, index)
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
        "window_minutes": int((deadline - current).total_seconds() // 60),
        "buffer_minutes": buffer_minutes,
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


