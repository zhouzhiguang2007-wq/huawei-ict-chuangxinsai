#!/usr/bin/env python3
"""Validate the canonical requirements object used by this skill."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional


ALLOWED_TRANSPORT = {"walk", "transit", "drive", "bike", "mixed", "unspecified"}
ALLOWED_PACE = {"relaxed", "balanced", "intensive", "unspecified"}
ALLOWED_BUDGET_SCOPE = {"total_trip", "per_person", "per_day", "unspecified"}


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


