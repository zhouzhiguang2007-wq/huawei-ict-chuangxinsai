"""Validate a complete, chronological, place-continuous travel route.

Usage: python validate_route_timeline.py route.json
       python validate_route_timeline.py < route.json

The checker is deliberately offline. A plausible timestamp is not proof that
an attraction is open or a transfer is available; those facts need research.
"""

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta


DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?[+-]\d{2}:\d{2}$")
SEGMENT_KINDS = {"gather", "transfer", "visit", "meal", "rest",
                 "check_in", "check_out", "free_time", "other"}


def validate_route(payload):
    """Return invalid, fail, incomplete, or pass plus individual checks.

    Contract:
      trip: start_date, end_date, days, start_place_id, end_place_id
      daily_routes[]: date, start_anchor, end_anchor, segments[]
      anchor: at (offset-aware ISO time or null), place_id (string or null)
      segment: id, kind, start, end; transfer has from_place_id,
        to_place_id, mode; other kinds have place_id. Visit also has
        visit_minutes and at least two distinct highlights.
      max_unexplained_gap_minutes: optional nonnegative integer (default 45)
      max_daily_unexplained_gap_minutes: optional nonnegative integer (default 60)

    Null fact values produce incomplete. Malformed types/formats produce
    invalid. Known contradictions and omitted expected dates produce fail.
    Explicit rest/free_time segments account for otherwise unexplained time.
    """
    report = {"status": "invalid", "checks": [], "issues": [],
              "missing_data": [], "errors": [], "summary": {}}

    def check(rule, status, message, ids=None):
        report["checks"].append({"rule": rule, "status": status,
                                 "message": message, "segment_ids": ids or []})

    def missing(label):
        check("missing_data", "unknown", label + "待补充")

    def place(value, label):
        if value is None:
            missing(label)
            return None
        if not isinstance(value, str) or not value.strip():
            report["errors"].append(label + "须为非空地点 ID 或 null")
            return None
        return value.strip()

    def day(value, label):
        if value is None:
            missing(label)
            return None
        if not isinstance(value, str) or not DATE_PATTERN.fullmatch(value):
            report["errors"].append(label + "须为 YYYY-MM-DD 或 null")
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            report["errors"].append(label + "不是有效日期")
            return None

    def moment(value, label):
        if value is None:
            missing(label)
            return None
        if not isinstance(value, str) or not TIME_PATTERN.fullmatch(value):
            report["errors"].append(label + "须为带时区偏移的 ISO 时间或 null")
            return None
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.utcoffset() is None:
                raise ValueError("missing offset")
            return parsed
        except ValueError:
            report["errors"].append(label + "不是有效时间")
            return None

    def integer(value, label, positive=False):
        if value is None:
            missing(label)
            return None
        if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0):
            report["errors"].append(label + ("须为正整数或 null" if positive else "须为非负整数或 null"))
            return None
        return value

    def gap_limit(key, default):
        value = payload.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            report["errors"].append(key + "须为非负整数")
            return default
        return value

    if not isinstance(payload, dict):
        report["errors"].append("顶层须为 JSON 对象")
        return report
    trip = payload.get("trip")
    routes = payload.get("daily_routes")
    routes_provided = routes is not None and isinstance(routes, list)
    if trip is None:
        missing("trip ")
        trip = {}
    elif not isinstance(trip, dict):
        report["errors"].append("trip 须为对象")
        trip = {}
    if routes is None:
        missing("daily_routes ")
        routes = []
    elif not isinstance(routes, list):
        report["errors"].append("daily_routes 须为数组")
        routes = []

    max_gap = gap_limit("max_unexplained_gap_minutes", 45)
    max_daily_gap = gap_limit("max_daily_unexplained_gap_minutes", 60)
    trip_start = day(trip.get("start_date"), "trip.start_date ")
    trip_end = day(trip.get("end_date"), "trip.end_date ")
    days = integer(trip.get("days"), "trip.days ", positive=True)
    start_place = place(trip.get("start_place_id"), "trip.start_place_id ")
    end_place = place(trip.get("end_place_id"), "trip.end_place_id ")

    expected = []
    if trip_start is not None and trip_end is not None:
        if trip_end < trip_start:
            check("trip_dates", "fail", "结束日期早于开始日期")
        else:
            expected = [trip_start + timedelta(days=i)
                        for i in range((trip_end - trip_start).days + 1)]
            if days is not None:
                check("trip_days", "pass" if days == len(expected) else "fail",
                      "天数须与起止日期的自然日数量一致")

    parsed_routes = []
    seen_dates = set()
    seen_ids = set()
    for route_index, route in enumerate(routes):
        prefix = "daily_routes[{}]".format(route_index)
        if not isinstance(route, dict):
            report["errors"].append(prefix + "须为对象")
            continue
        route_day = day(route.get("date"), prefix + ".date ")
        if route_day is not None:
            if route_day in seen_dates:
                report["errors"].append(prefix + ".date 重复")
            seen_dates.add(route_day)
        start_anchor = route.get("start_anchor")
        end_anchor = route.get("end_anchor")
        if start_anchor is None:
            missing(prefix + ".start_anchor ")
            start_anchor = {}
        elif not isinstance(start_anchor, dict):
            report["errors"].append(prefix + ".start_anchor 须为对象")
            start_anchor = {}
        if end_anchor is None:
            missing(prefix + ".end_anchor ")
            end_anchor = {}
        elif not isinstance(end_anchor, dict):
            report["errors"].append(prefix + ".end_anchor 须为对象")
            end_anchor = {}
        first_at = moment(start_anchor.get("at"), prefix + ".start_anchor.at ")
        first_place = place(start_anchor.get("place_id"), prefix + ".start_anchor.place_id ")
        last_at = moment(end_anchor.get("at"), prefix + ".end_anchor.at ")
        last_place = place(end_anchor.get("place_id"), prefix + ".end_anchor.place_id ")
        if first_at is not None and route_day is not None:
            check("anchor_date", "pass" if first_at.date() == route_day else "fail",
                  prefix + " 起点时间的当地日期须等于 date")
        if first_at is not None and last_at is not None:
            check("anchor_order", "pass" if first_at < last_at else "fail",
                  prefix + " 终点时间须晚于起点时间")

        segments = route.get("segments")
        if segments is None:
            missing(prefix + ".segments ")
            segments = []
        elif not isinstance(segments, list):
            report["errors"].append(prefix + ".segments 须为数组")
            segments = []
        if not segments:
            check("route_coverage", "unknown", prefix + " 没有可核对的时间线")
        parsed_segments = []
        for seg_index, seg in enumerate(segments):
            label = prefix + ".segments[{}]".format(seg_index)
            if not isinstance(seg, dict):
                report["errors"].append(label + "须为对象")
                continue
            ident = seg.get("id")
            if ident is None:
                missing(label + ".id ")
                ident = label
            elif not isinstance(ident, str) or not ident.strip():
                report["errors"].append(label + ".id 须为非空字符串")
                ident = label
            elif ident in seen_ids:
                report["errors"].append("segment id 重复：" + ident)
            seen_ids.add(ident)
            kind = seg.get("kind")
            if kind is None:
                missing(label + ".kind ")
            elif not isinstance(kind, str) or not kind.strip():
                report["errors"].append(label + ".kind 须为非空字符串")
                kind = None
            elif kind not in SEGMENT_KINDS:
                report["errors"].append(label + ".kind 不在允许的段类型中")
                kind = None
            started = moment(seg.get("start"), label + ".start ")
            ended = moment(seg.get("end"), label + ".end ")
            if started is not None and ended is not None:
                check("segment_duration", "pass" if started < ended else "fail",
                      label + " 结束时间须晚于开始时间", [ident])
            if kind == "transfer":
                origin = place(seg.get("from_place_id"), label + ".from_place_id ")
                destination = place(seg.get("to_place_id"), label + ".to_place_id ")
                mode = seg.get("mode")
                if mode is None:
                    missing(label + ".mode ")
                elif not isinstance(mode, str) or not mode.strip():
                    report["errors"].append(label + ".mode 须为非空字符串或 null")
            else:
                origin = destination = place(seg.get("place_id"), label + ".place_id ")
            if kind == "visit":
                visit_minutes = integer(seg.get("visit_minutes"), label + ".visit_minutes ", positive=True)
                highlights = seg.get("highlights")
                if highlights is None:
                    missing(label + ".highlights ")
                elif not isinstance(highlights, list):
                    report["errors"].append(label + ".highlights 须为数组或 null")
                elif any(not isinstance(h, str) or not h.strip() for h in highlights):
                    report["errors"].append(label + ".highlights 每项须为非空文字")
                else:
                    distinct = {h.strip() for h in highlights}
                    check("visit_highlights", "pass" if len(distinct) >= 2 else "fail",
                          label + " 须有至少两个不同的游览亮点", [ident])
                if started is not None and ended is not None and visit_minutes is not None:
                    actual = (ended - started).total_seconds() / 60
                    check("visit_minutes", "pass" if actual == visit_minutes else "fail",
                          label + " 标注游览分钟数须等于起止时间之差", [ident])
            parsed_segments.append({"id": ident, "start": started, "end": ended,
                                    "origin": origin, "destination": destination})

        if parsed_segments:
            first = parsed_segments[0]
            last = parsed_segments[-1]
            if first_at is not None and first["start"] is not None:
                check("start_anchor_time", "pass" if first_at == first["start"] else "fail",
                      prefix + " 起点时间须贴合第一段开始", [first["id"]])
            if first_place is not None and first["origin"] is not None:
                check("start_anchor_place", "pass" if first_place == first["origin"] else "fail",
                      prefix + " 起点地点须接上第一段", [first["id"]])
            if last_at is not None and last["end"] is not None:
                check("end_anchor_time", "pass" if last_at == last["end"] else "fail",
                      prefix + " 终点时间须贴合最后一段结束", [last["id"]])
            if last_place is not None and last["destination"] is not None:
                check("end_anchor_place", "pass" if last_place == last["destination"] else "fail",
                      prefix + " 终点地点须接上最后一段", [last["id"]])

        known_gap_sum = 0
        unknown_gap = False
        for previous, current in zip(parsed_segments, parsed_segments[1:]):
            ids = [previous["id"], current["id"]]
            if previous["destination"] is not None and current["origin"] is not None:
                check("place_continuity", "pass" if previous["destination"] == current["origin"] else "fail",
                      prefix + " 相邻两段地点须接续", ids)
            if previous["end"] is None or current["start"] is None:
                unknown_gap = True
                continue
            gap = (current["start"] - previous["end"]).total_seconds() / 60
            if gap < 0:
                check("time_overlap", "fail", prefix + " 相邻两段时间重叠", ids)
            else:
                known_gap_sum += gap
                check("unexplained_gap", "pass" if gap <= max_gap else "fail",
                      prefix + " 未说明空档 {:.1f} 分钟，上限 {} 分钟".format(gap, max_gap), ids)
        if parsed_segments:
            check("daily_unexplained_gap", "unknown" if unknown_gap else
                  "pass" if known_gap_sum <= max_daily_gap else "fail",
                  prefix + " 已知未说明空档合计 {:.1f} 分钟，上限 {} 分钟".format(
                      known_gap_sum, max_daily_gap))
        parsed_routes.append({"date": route_day, "first_at": first_at,
                              "first_place": first_place, "last_at": last_at,
                              "last_place": last_place})

    known_route_dates = [route["date"] for route in parsed_routes if route["date"] is not None]
    if known_route_dates != sorted(known_route_dates):
        check("date_order", "fail", "daily_routes 须按旅行日期顺序排列")
    if expected and routes_provided:
        for expected_day in expected:
            status = ("pass" if expected_day in known_route_dates else
                      "unknown" if any(r["date"] is None for r in parsed_routes) else "fail")
            check("expected_day", status,
                  "旅行日期 {} 须有一条逐日线路".format(expected_day.isoformat()))
        for actual_day in known_route_dates:
            if actual_day not in expected:
                check("extra_day", "fail", "线路日期 {} 超出行程范围".format(actual_day.isoformat()))
    if parsed_routes and trip_start is not None:
        first = next((r for r in parsed_routes if r["date"] == trip_start), None)
        if first is not None and start_place is not None and first["first_place"] is not None:
            check("trip_start_place", "pass" if start_place == first["first_place"] else "fail",
                  "首日起点须接上出发地点")
    if parsed_routes and trip_end is not None:
        last = next((r for r in parsed_routes if r["date"] == trip_end), None)
        if last is not None and end_place is not None and last["last_place"] is not None:
            check("trip_end_place", "pass" if end_place == last["last_place"] else "fail",
                  "末日终点须接上离开地点")
    ordered = sorted((r for r in parsed_routes if r["date"] is not None), key=lambda r: r["date"])
    for previous, current in zip(ordered, ordered[1:]):
        if current["date"] != previous["date"] + timedelta(days=1):
            continue  # Missing dates are reported by expected_day.
        if previous["last_place"] is not None and current["first_place"] is not None:
            check("overnight_place", "pass" if previous["last_place"] == current["first_place"] else "fail",
                  "{} 至 {} 的过夜地点须连续".format(previous["date"], current["date"]))
        if previous["last_at"] is not None and current["first_at"] is not None:
            check("overnight_time", "pass" if previous["last_at"] <= current["first_at"] else "fail",
                  "次日起点不得早于前一天终点")

    statuses = [item["status"] for item in report["checks"]]
    report["status"] = ("invalid" if report["errors"] else "fail" if "fail" in statuses
                        else "incomplete" if "unknown" in statuses else "pass")
    report["issues"] = [c for c in report["checks"] if c["status"] == "fail"]
    report["missing_data"] = [c for c in report["checks"] if c["status"] == "unknown"]
    report["summary"] = {"failed": len(report["issues"]),
                         "unknown": len(report["missing_data"]),
                         "passed": statuses.count("pass")}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="JSON 文件路径；省略则读取标准输入")
    args = parser.parse_args()
    try:
        if args.path:
            with open(args.path, encoding="utf-8") as stream:
                payload = json.load(stream)
        else:
            payload = json.load(sys.stdin)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "invalid", "errors": [str(exc)]}, ensure_ascii=False))
        return 2
    report = validate_route(payload)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "invalid" else 0


if __name__ == "__main__":
    sys.exit(main())
