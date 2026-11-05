"""Normalize 12306-mcp `get-tickets` output into structured railway legs.

12306-mcp (community MCP, npm `12306-mcp`) returns a Markdown-ish text block:

    车次|出发站 -> 到达站|出发时间 -> 到达时间|历时
    G1812 洛阳龙门(telecode:LLF) -> 开封北(telecode:KBF) 08:05 -> 09:12 历时：01:07
    - 商务座: 剩余1张票 281元
    - 一等座: 有票 146元
    - 二等座: 有票 91元
    - 无座: 无票 91元

This module turns that text into deterministic JSON so downstream skills
(planner, replanner, review, time-pocket) do not each re-invent parsing and
so `lookup_status` is decided from evidence instead of guessed.

Pure standard library; no network, no MCP process. Python 3.9+.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))

SOURCE = "12306-mcp:get-tickets"

_TRAIN_LINE = re.compile(
    r"^(?P<train>[A-Z]\d{1,4}|[A-Z]{1,3}\d{1,4})\s+"
    r"(?P<from>.+?)\s*->\s*(?P<to>.+?)\s+"
    r"(?P<depart>\d{2}:\d{2})\s*->\s*(?P<arrive>\d{2}:\d{2})\s*"
    r"历时\s*[：:]\s*(?P<dh>\d{1,2}):(?P<dm>\d{2})",
    re.MULTILINE,
)

_TELECODE = re.compile(r"\(telecode\s*:\s*(?P<code>[A-Z]{2,4})\)\s*$", re.IGNORECASE)

_SEAT_LINE = re.compile(
    r"^-\s*(?P<cls>[^:：]+?)\s*[:：]\s*(?P<avail>.+?)\s+(?P<fare>\d+(?:\.\d+)?)\s*元"
)

_BLOCKED_MARKERS = ("验证码", "captcha", "登录", "login required", "blocked", "访问过于频繁")
_NO_RESULT_MARKERS = ("未找到", "没有查询到", "no result", "no train", "无列车", "暂无")

_AVAILABILITY_RULES = (
    ("无票", "无票"),
    ("候补", "候补"),
    ("有票", "有票"),
    ("有 ", "有票"),
)


def _strip_telecode(name):
    name = name.strip()
    code = None
    match = _TELECODE.search(name)
    if match:
        code = match.group("code").upper()
        name = name[: match.start()].strip()
    return name, code


def _normalize_availability(text):
    text = text.strip()
    count = re.search(r"剩余\s*(\d+)\s*张", text)
    if "无票" in text:
        return "无票", 0
    if "候补" in text:
        return "候补", None
    if count:
        return "有票", int(count.group(1))
    for marker, label in _AVAILABILITY_RULES:
        if marker in text:
            return label, None
    return text, None


def _duration_minutes(dh, dm):
    return int(dh) * 60 + int(dm)


def detect_status(text, tool_available=True):
    """Decide lookup_status from raw tool text."""
    if not tool_available:
        return "tool_unavailable"
    if not text or not text.strip():
        return "tool_unavailable"
    lowered = text.lower()
    if any(marker.lower() in lowered for marker in _BLOCKED_MARKERS):
        return "blocked"
    if any(marker.lower() in lowered for marker in _NO_RESULT_MARKERS):
        return "no_result"
    if _TRAIN_LINE.search(text):
        return "verified"
    return "no_result"


def normalize(text, *, date, from_station, to_station,
              queried_at=None, tool_available=True, source=SOURCE):
    """Parse get-tickets text into structured legs plus provenance."""
    status = detect_status(text, tool_available=tool_available)
    if queried_at is None:
        queried_at = datetime.now(CST).isoformat(timespec="seconds")

    legs = []
    current = None
    if status == "verified":
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            train_match = _TRAIN_LINE.match(line)
            if train_match:
                frm, frm_code = _strip_telecode(train_match.group("from"))
                to, to_code = _strip_telecode(train_match.group("to"))
                current = {
                    "train_no": train_match.group("train"),
                    "from_station": frm,
                    "from_telecode": frm_code,
                    "to_station": to,
                    "to_telecode": to_code,
                    "depart": train_match.group("depart"),
                    "arrive": train_match.group("arrive"),
                    "duration_minutes": _duration_minutes(
                        train_match.group("dh"), train_match.group("dm")),
                    "seats": [],
                }
                legs.append(current)
                continue
            seat_match = _SEAT_LINE.match(line)
            if seat_match and current is not None:
                availability, remaining = _normalize_availability(seat_match.group("avail"))
                current["seats"].append({
                    "class": seat_match.group("cls").strip(),
                    "availability": availability,
                    "remaining": remaining,
                    "fare_cny": _number(seat_match.group("fare")),
                })
    return {
        "lookup_status": status,
        "source": source,
        "queried_at": queried_at,
        "date": date,
        "requested_from": from_station,
        "requested_to": to_station,
        "leg_count": len(legs),
        "legs": legs,
    }


def _number(value):
    amount = float(value)
    return int(amount) if amount.is_integer() else amount


def cheapest_seat(leg, preferred_classes=None):
    """Return the cheapest bookable seat (availability is not 无票)."""
    candidates = [s for s in leg.get("seats", [])
                  if s.get("availability") in ("有票", "候补")]
    if preferred_classes:
        preferred = [s for s in candidates if s.get("class") in preferred_classes]
        if preferred:
            candidates = preferred
    if not candidates:
        return None
    return min(candidates, key=lambda s: s.get("fare_cny", float("inf")))


def choose_leg(normalized, *, earliest=None, latest=None, max_duration_minutes=None):
    """Pick the earliest departure inside a window; deterministic tie-break."""
    legs = normalized.get("legs", [])
    if earliest:
        legs = [l for l in legs if l["depart"] >= earliest]
    if latest:
        legs = [l for l in legs if l["depart"] <= latest]
    if max_duration_minutes is not None:
        legs = [l for l in legs if l["duration_minutes"] <= max_duration_minutes]
    if not legs:
        return None
    return sorted(legs, key=lambda l: (l["depart"], l["arrive"]))[0]


def to_route_segments(normalized, leg, *, from_place_id, to_place_id,
                      date, segment_id="rail-1"):
    """Map one chosen leg into the transfer segment shape used by
    validate_route_timeline.py, keeping fare/seat evidence alongside."""
    if leg is None:
        return None
    seat = cheapest_seat(leg)
    return {
        "id": segment_id,
        "kind": "transfer",
        "from_place_id": from_place_id,
        "to_place_id": to_place_id,
        "mode": "rail",
        "start": date + "T" + leg["depart"] + ":00+08:00",
        "end": date + "T" + leg["arrive"] + ":00+08:00",
        "train_no": leg["train_no"],
        "duration_minutes": leg["duration_minutes"],
        "evidence": {
            "source": normalized.get("source"),
            "queried_at": normalized.get("queried_at"),
            "lookup_status": normalized.get("lookup_status"),
        },
        "fare": None if seat is None else {
            "currency": "CNY",
            "amount": seat["fare_cny"],
            "seat_class": seat["class"],
            "availability": seat["availability"],
            "remaining": seat.get("remaining"),
            "note": "fare and remaining tickets can change before payment",
        },
    }


def session_payload(normalized):
    """Shape to store via session_put (Module B) for downstream skills."""
    return {
        "railway": normalized,
        "verified": normalized.get("lookup_status") == "verified",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Normalize 12306-mcp get-tickets text into structured JSON.")
    parser.add_argument("--file", required=True, help="path to raw MCP text output")
    parser.add_argument("--date", required=True)
    parser.add_argument("--from", dest="from_station", required=True)
    parser.add_argument("--to", dest="to_station", required=True)
    parser.add_argument("--queried-at", default=None)
    parser.add_argument("--tool-available", action="store_true", default=True)
    parser.add_argument("--tool-unavailable", dest="tool_available",
                        action="store_false")
    args = parser.parse_args(argv)

    with open(args.file, "r", encoding="utf-8") as handle:
        text = handle.read()
    result = normalize(
        text,
        date=args.date,
        from_station=args.from_station,
        to_station=args.to_station,
        queried_at=args.queried_at,
        tool_available=args.tool_available,
    )
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if result["lookup_status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())