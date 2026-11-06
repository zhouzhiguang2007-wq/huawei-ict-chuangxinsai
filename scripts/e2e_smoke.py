"""端到端闭环 smoke：需求 → 知识 → 会话 → 铁路 → 路线校验 → 复核输入。

不依赖宿主、不联网、只用临时 SQLite，用于证明「组件串起来能跑通」，并为
现场人工验收提供可重复的基线。真实宿主内的对话触发仍需人工验收。

用法：
    python scripts/e2e_smoke.py
    python scripts/e2e_smoke.py --json

退出码：0 全部通过；1 有步骤失败。
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT, ROOT / "skills" / "multi-platform-travel-planner" / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from travel_shared.db import init_db  # noqa: E402
from travel_shared.tools import TravelTools  # noqa: E402

import normalize_railway_mcp as rail  # noqa: E402
import validate_route_timeline as route_checker  # noqa: E402

SAMPLE_TICKETS = """车次|出发站 -> 到达站|出发时间 -> 到达时间|历时
G1812 洛阳龙门(telecode:LLF) -> 开封北(telecode:KBF) 08:05 -> 09:12 历时：01:07
- 二等座: 有票 91元
"""


def _context():
    return {
        "schema_version": "1.0",
        "trip_id": "e2e-trip",
        "skill": "travel-requirement-analysis",
        "requirements": {
            "destination": {"city": "开封"},
            "dates": {"start_date": "2026-11-10", "days": 1},
            "travelers": {"total": 2, "adults": 2},
            "budget": {"amount": 800, "currency": "CNY",
                       "scope": "total_trip", "hard_limit": True},
            "preferences": {"pace": "balanced"},
        },
        "payload": {},
    }


def _route_payload(segment):
    return {
        "trip": {"start_date": "2026-11-10", "end_date": "2026-11-10",
                 "days": 1, "start_place_id": "luoyanglongmen",
                 "end_place_id": "qingming"},
        "daily_routes": [{
            "date": "2026-11-10",
            "start_anchor": {"at": "2026-11-10T08:05:00+08:00",
                             "place_id": "luoyanglongmen"},
            "end_anchor": {"at": "2026-11-10T11:00:00+08:00",
                           "place_id": "qingming"},
            "segments": [
                segment,
                {"id": "walk-1", "kind": "transfer",
                 "start": "2026-11-10T09:12:00+08:00",
                 "end": "2026-11-10T09:20:00+08:00",
                 "from_place_id": "kaifengbei", "to_place_id": "qingming",
                 "mode": "walk"},
                {"id": "visit-1", "kind": "visit",
                 "start": "2026-11-10T09:20:00+08:00",
                 "end": "2026-11-10T11:00:00+08:00",
                 "place_id": "qingming", "visit_minutes": 100,
                 "highlights": ["虹桥", "汴河"]},
            ],
        }],
    }


def run():
    """执行闭环，返回 (ok, steps)。"""
    steps = []

    def record(name, ok, detail):
        steps.append({"step": name, "ok": bool(ok), "detail": detail})

    with tempfile.TemporaryDirectory() as tmp:
        internal = str(Path(tmp) / "internal.sqlite3")
        prefs = str(Path(tmp) / "preferences.sqlite3")
        init_db(internal)
        tools = TravelTools(prefs, internal_db_path=internal)
        user = "e2e-user"

        seeded = tools.handle({"action": "seed"}, user_id=user)
        record("seed", seeded["status"] == "ok",
               seeded["data"].get("guided_questions", {}))

        step1 = tools.handle({"action": "questionnaire_get_step", "step": 1},
                             user_id=user)
        record("questionnaire.step1",
               step1["status"] == "ok" and step1["data"].get("found") is True,
               {"dimension": step1["data"].get("dimension")})

        match = tools.handle({"action": "registry_query", "query": "拍照出片"},
                             user_id=user)
        matched = [s["skill_name"] for s in match["data"].get("matched_skills", [])]
        record("registry.photo", "x-xiake" in matched, matched)

        know = tools.handle({"action": "knowledge_query", "category": "city_info",
                             "key": "开封"}, user_id=user)
        record("knowledge.kaifeng", know["data"].get("found") is True,
               {"spots": len(know["data"].get("value", {}).get("known_spots", []))})

        put = tools.handle({
            "action": "session_put", "trip_id": "e2e-trip",
            "skill": "travel-requirement-analysis", "stage": "confirmed",
            "key": "requirements",
            "value": _context()["requirements"],
        }, user_id=user)
        req = tools.handle({"action": "session_get_requirements",
                            "trip_id": "e2e-trip"}, user_id=user)
        record("session.roundtrip",
               put["status"] == "ok" and req["data"].get("found") is True,
               req["data"].get("requirements", {}).get("destination"))

        normalized = rail.normalize(SAMPLE_TICKETS, date="2026-11-10",
                                    from_station="洛阳", to_station="开封",
                                    queried_at="2026-11-05T19:00:00+08:00")
        leg = rail.choose_leg(normalized, earliest="08:00", latest="10:00")
        record("railway.normalize",
               normalized["lookup_status"] == "verified" and leg is not None,
               None if leg is None else {"train": leg["train_no"],
                                          "depart": leg["depart"]})

        segment = rail.to_route_segments(
            normalized, leg, from_place_id="luoyanglongmen",
            to_place_id="kaifengbei", date="2026-11-10", segment_id="rail-1")
        record("railway.segment", segment is not None,
               None if segment is None else {"mode": segment.get("mode")})

        validation = route_checker.validate_route(_route_payload(segment))
        record("route.validate", validation["status"] == "pass",
               {"status": validation["status"],
                "issues": len(validation.get("issues", []))})

        prepared = tools.handle({"action": "prepare", "context": _context()},
                                user_id=user)
        record("prepare", prepared["status"] == "ok",
               {"status": prepared["status"]})

        stored = tools.handle({"action": "session_put", "trip_id": "e2e-trip",
                               "skill": "multi-platform-travel-planner",
                               "stage": "verified", "key": "railway_legs",
                               "value": rail.session_payload(normalized)},
                              user_id=user)
        record("session.railway", stored["status"] == "ok",
               {"verified": json.loads(json.dumps(normalized))["lookup_status"]})

    return all(s["ok"] for s in steps), steps


def main(argv=None):
    parser = argparse.ArgumentParser(description="端到端闭环 smoke")
    parser.add_argument("--json", dest="as_json", action="store_true")
    args = parser.parse_args(argv)

    ok, steps = run()
    if args.as_json:
        print(json.dumps({"ok": ok, "steps": steps}, ensure_ascii=False, indent=2))
    else:
        for item in steps:
            print(("PASS " if item["ok"] else "FAIL ") + item["step"],
                  "" if item["detail"] is None else item["detail"])
        print("结果:", "全部通过" if ok else "存在失败")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())