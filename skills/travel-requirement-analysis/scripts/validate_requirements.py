#!/usr/bin/env python3
"""Validate the canonical requirements object used by this skill."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional


ALLOWED_TRANSPORT = {"walk", "transit", "drive", "bike", "mixed", "unspecified"}
ALLOWED_PACE = {"relaxed", "balanced", "intensive", "unspecified"}
ALLOWED_BUDGET_SCOPE = {"total_trip", "per_person", "per_day", "unspecified"}
ALLOWED_LOCATION_STATUS = {"unknown", "ambiguous", "confirmed"}
ALLOWED_DEPARTURE_STATUS = {"unknown", "window", "flexible"}


def _parse_date(value: Any, field: str, errors: List[str]) -> Optional[date]:
    if value is None:
        return None
    if not isinstance(value, str):
        errors.append(f"{field} must be a string or null")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"{field} must use YYYY-MM-DD")
        return None


def _non_negative_integer(value: Any, field: str, errors: List[str]) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
        errors.append(f"{field} must be a non-negative integer or null")


def validate_requirements(data: Any) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    missing: List[str] = []

    if not isinstance(data, dict):
        return {"valid": False, "ready": False, "errors": ["root must be an object"], "warnings": [], "missing_fields": []}

    destination = data.get("destination")
    dates = data.get("dates")
    travelers = data.get("travelers")
    budget = data.get("budget")
    preferences = data.get("preferences")
    task_scope = data.get("task_scope", "full_trip")
    time_plan_required = data.get("time_plan_required", False)
    if not isinstance(time_plan_required, bool):
        errors.append("time_plan_required must be a boolean")

    if not isinstance(destination, dict):
        errors.append("destination must be an object")
        destination = {}
    city = destination.get("city")
    if city is None or city == "":
        missing.append("destination.city")
    elif not isinstance(city, str):
        errors.append("destination.city must be a string or null")

    if not isinstance(dates, dict):
        errors.append("dates must be an object")
        dates = {}
    start = _parse_date(dates.get("start_date"), "dates.start_date", errors)
    end = _parse_date(dates.get("end_date"), "dates.end_date", errors)
    days = dates.get("days")
    if start is None:
        missing.append("dates.start_date")
    if days is None:
        missing.append("dates.days")
    elif isinstance(days, bool) or not isinstance(days, int) or days <= 0:
        errors.append("dates.days must be a positive integer or null")
    if start and end:
        calendar_days = (end - start).days + 1
        if calendar_days <= 0:
            errors.append("dates.end_date must not be earlier than dates.start_date")
        elif isinstance(days, int) and not isinstance(days, bool) and days != calendar_days:
            errors.append("dates.days conflicts with inclusive start/end dates")

    departure_availability = dates.get("departure_availability")
    if departure_availability is not None and not isinstance(departure_availability, dict):
        errors.append("dates.departure_availability must be an object or null")
    elif isinstance(departure_availability, dict):
        availability_status = departure_availability.get("status", "unknown")
        if availability_status not in ALLOWED_DEPARTURE_STATUS:
            errors.append("dates.departure_availability.status is not supported")
        bounds = []
        for key in ("earliest", "latest"):
            value = departure_availability.get(key)
            if value is not None:
                if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
                    errors.append(f"dates.departure_availability.{key} must use HH:MM or null")
                else:
                    bounds.append(value)
        if availability_status == "window" and not bounds:
            errors.append("dates.departure_availability.window needs a time bound")
        if availability_status in {"unknown", "flexible"} and bounds:
            errors.append("dates.departure_availability time bounds conflict with status")
        if len(bounds) == 2 and bounds[0] > bounds[1]:
            errors.append("dates.departure_availability earliest must not exceed latest")

    if travelers is not None:
        if not isinstance(travelers, dict):
            errors.append("travelers must be an object or null")
        else:
            for key in ("total", "adults", "children", "older_adults"):
                _non_negative_integer(travelers.get(key), f"travelers.{key}", errors)
            parts = [travelers.get(key) for key in ("adults", "children", "older_adults")]
            total = travelers.get("total")
            if isinstance(total, int) and not isinstance(total, bool) and all(isinstance(v, int) and not isinstance(v, bool) for v in parts):
                if total != sum(parts):
                    errors.append("travelers.total conflicts with traveler breakdown")

    if budget is not None:
        if not isinstance(budget, dict):
            errors.append("budget must be an object or null")
        else:
            amount = budget.get("amount")
            if amount is not None and (isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0):
                errors.append("budget.amount must be a non-negative number or null")
            currency = budget.get("currency")
            if currency is not None and (not isinstance(currency, str) or len(currency) != 3 or currency.upper() != currency):
                errors.append("budget.currency must be a three-letter uppercase code or null")
            scope = budget.get("scope")
            if scope is not None and scope not in ALLOWED_BUDGET_SCOPE:
                errors.append("budget.scope is not supported")

    if preferences is not None:
        if not isinstance(preferences, dict):
            errors.append("preferences must be an object or null")
        else:
            pace = preferences.get("pace")
            if pace is not None and pace not in ALLOWED_PACE:
                errors.append("preferences.pace is not supported")
            modes = preferences.get("transport_modes", [])
            if not isinstance(modes, list) or any(mode not in ALLOWED_TRANSPORT for mode in modes):
                errors.append("preferences.transport_modes contains an unsupported value")

    unknown = data.get("unknown_fields", [])
    if not isinstance(unknown, list) or any(not isinstance(item, str) for item in unknown):
        errors.append("unknown_fields must be an array of strings")
    elif task_scope == "full_trip":
        missing.extend(field for field in unknown if field in {
            "departure_location.detail", "return_location.detail",
            "departure_location.campus", "return_location.campus",  # older payloads
        })

    location_resolution = data.get("location_resolution")
    if location_resolution is not None:
        if not isinstance(location_resolution, dict):
            errors.append("location_resolution must be an object or null")
        else:
            location_status = location_resolution.get("status", "unknown")
            if location_status not in ALLOWED_LOCATION_STATUS:
                errors.append("location_resolution.status is not supported")
            elif location_status == "ambiguous" and task_scope == "full_trip":
                ambiguous_fields = location_resolution.get("ambiguous_fields", [])
                if not isinstance(ambiguous_fields, list) or any(not isinstance(item, str) for item in ambiguous_fields):
                    errors.append("location_resolution.ambiguous_fields must be an array of strings")
                else:
                    missing.extend(ambiguous_fields or ["location_resolution"])

    departure_time_unknown = departure_availability is None or (
        isinstance(departure_availability, dict) and departure_availability.get("status", "unknown") == "unknown"
    )
    if departure_time_unknown and (data.get("departure_location") or time_plan_required):
        warnings.append("departure availability is unknown; exact outbound timing cannot be finalized")

    if task_scope == "full_trip":
        if time_plan_required and departure_time_unknown:
            missing.append("dates.departure_availability")
        if travelers is None or (isinstance(travelers, dict) and travelers.get("total") is None):
            missing.append("travelers.total")
        if budget is None or (isinstance(budget, dict) and budget.get("amount") is None and not budget.get("no_limit")):
            missing.append("budget.amount")
        if budget is None or (isinstance(budget, dict) and budget.get("scope") in (None, "unspecified") and not budget.get("no_limit")):
            missing.append("budget.scope")

    if travelers is None or (isinstance(travelers, dict) and travelers.get("total") is None):
        warnings.append("traveler count is unknown; accommodation and total-cost planning may require clarification")
    if budget is None or (isinstance(budget, dict) and budget.get("amount") is None):
        warnings.append("budget amount is unknown; strict budget validation is unavailable")

    missing = list(dict.fromkeys(missing))
    return {
        "valid": not errors,
        "ready": not errors and not missing,
        "errors": errors,
        "warnings": warnings,
        "missing_fields": missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", help="JSON file; reads stdin when omitted")
    args = parser.parse_args()
    try:
        raw = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
        result = validate_requirements(json.loads(raw))
    except (OSError, json.JSONDecodeError) as exc:
        result = {"valid": False, "ready": False, "errors": [str(exc)], "warnings": [], "missing_fields": []}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


