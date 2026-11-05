"""Tests for normalize_railway_mcp (unittest style; CI runs this directly)."""

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from normalize_railway_mcp import (  # noqa: E402
    cheapest_seat, choose_leg, detect_status, main, normalize,
    session_payload, to_route_segments,
)

SAMPLE = """车次|出发站 -> 到达站|出发时间 -> 到达时间|历时
G1812 洛阳龙门(telecode:LLF) -> 开封北(telecode:KBF) 08:05 -> 09:12 历时：01:07
- 商务座: 剩余1张票 281元
- 一等座: 有票 146元
- 二等座: 有票 91元
- 无座: 无票 91元
G2260 洛阳龙门(telecode:LLF) -> 开封北(telecode:KBF) 11:16 -> 12:19 历时：01:03
- 二等座: 有票 91元
- 一等座: 无票 146元
G1880 洛阳龙门(telecode:LLF) -> 开封北(telecode:KBF) 18:04 -> 19:05 历时：01:01
- 二等座: 候补 80元
"""


class DetectStatusTests(unittest.TestCase):

    def test_verified_when_trains_parsed(self):
        self.assertEqual(detect_status(SAMPLE), "verified")

    def test_no_result_markers(self):
        self.assertEqual(detect_status("未找到符合条件的车次"), "no_result")
        self.assertEqual(detect_status("No result found"), "no_result")

    def test_blocked_markers(self):
        self.assertEqual(detect_status("请完成验证码后重试"), "blocked")
        self.assertEqual(detect_status("captcha required"), "blocked")

    def test_empty_is_tool_unavailable(self):
        self.assertEqual(detect_status(""), "tool_unavailable")
        self.assertEqual(detect_status("   "), "tool_unavailable")

    def test_explicit_tool_unavailable(self):
        self.assertEqual(detect_status(SAMPLE, tool_available=False),
                         "tool_unavailable")


class NormalizeTests(unittest.TestCase):

    def setUp(self):
        self.normalized = normalize(
            SAMPLE, date="2026-11-10", from_station="洛阳", to_station="开封",
            queried_at="2026-11-05T19:00:00+08:00")

    def test_status_and_provenance(self):
        self.assertEqual(self.normalized["lookup_status"], "verified")
        self.assertEqual(self.normalized["source"], "12306-mcp:get-tickets")
        self.assertEqual(self.normalized["queried_at"],
                         "2026-11-05T19:00:00+08:00")
        self.assertEqual(self.normalized["date"], "2026-11-10")
        self.assertEqual(self.normalized["requested_from"], "洛阳")
        self.assertEqual(self.normalized["requested_to"], "开封")

    def test_leg_count(self):
        self.assertEqual(self.normalized["leg_count"], 3)

    def test_train_fields_and_telecode(self):
        leg = self.normalized["legs"][0]
        self.assertEqual(leg["train_no"], "G1812")
        self.assertEqual(leg["from_station"], "洛阳龙门")
        self.assertEqual(leg["from_telecode"], "LLF")
        self.assertEqual(leg["to_station"], "开封北")
        self.assertEqual(leg["to_telecode"], "KBF")
        self.assertEqual(leg["depart"], "08:05")
        self.assertEqual(leg["arrive"], "09:12")

    def test_duration_minutes(self):
        legs = self.normalized["legs"]
        self.assertEqual(legs[0]["duration_minutes"], 67)
        self.assertEqual(legs[1]["duration_minutes"], 63)
        self.assertEqual(legs[2]["duration_minutes"], 61)

    def test_seat_parsing(self):
        seats = {s["class"]: s for s in self.normalized["legs"][0]["seats"]}
        self.assertEqual(seats["商务座"]["availability"], "有票")
        self.assertEqual(seats["商务座"]["remaining"], 1)
        self.assertEqual(seats["商务座"]["fare_cny"], 281)
        self.assertEqual(seats["一等座"]["remaining"], None)
        self.assertEqual(seats["无座"]["availability"], "无票")
        self.assertEqual(seats["无座"]["remaining"], 0)

    def test_waitlist_availability(self):
        seats = {s["class"]: s for s in self.normalized["legs"][2]["seats"]}
        self.assertEqual(seats["二等座"]["availability"], "候补")

    def test_empty_text_no_legs(self):
        result = normalize("", date="2026-11-10",
                           from_station="洛阳", to_station="开封")
        self.assertEqual(result["lookup_status"], "tool_unavailable")
        self.assertEqual(result["leg_count"], 0)

    def test_no_result_has_no_legs(self):
        result = normalize("未找到符合条件的车次", date="2026-11-10",
                           from_station="洛阳", to_station="开封")
        self.assertEqual(result["lookup_status"], "no_result")
        self.assertEqual(result["legs"], [])


class SelectAndMapTests(unittest.TestCase):

    def setUp(self):
        self.normalized = normalize(
            SAMPLE, date="2026-11-10", from_station="洛阳", to_station="开封",
            queried_at="2026-11-05T19:00:00+08:00")

    def test_cheapest_seat_skips_sold_out(self):
        leg = self.normalized["legs"][0]
        seat = cheapest_seat(leg)
        self.assertEqual(seat["class"], "二等座")
        self.assertEqual(seat["fare_cny"], 91)

    def test_cheapest_seat_prefers_class_when_available(self):
        leg = self.normalized["legs"][0]
        seat = cheapest_seat(leg, preferred_classes=["一等座"])
        self.assertEqual(seat["class"], "一等座")
        self.assertEqual(seat["fare_cny"], 146)

    def test_choose_leg_window(self):
        leg = choose_leg(self.normalized, earliest="09:00", latest="12:00")
        self.assertEqual(leg["train_no"], "G2260")

    def test_choose_leg_max_duration(self):
        leg = choose_leg(self.normalized, max_duration_minutes=63)
        self.assertEqual(leg["train_no"], "G2260")

    def test_choose_leg_none(self):
        self.assertIsNone(choose_leg(self.normalized, earliest="23:00"))

    def test_to_route_segments_shape(self):
        leg = self.normalized["legs"][0]
        segment = to_route_segments(
            self.normalized, leg, from_place_id="luoyanglongmen",
            to_place_id="kaifengbei", date="2026-11-10", segment_id="rail-1")
        self.assertEqual(segment["kind"], "transfer")
        self.assertEqual(segment["mode"], "rail")
        self.assertEqual(segment["start"], "2026-11-10T08:05:00+08:00")
        self.assertEqual(segment["end"], "2026-11-10T09:12:00+08:00")
        self.assertEqual(segment["train_no"], "G1812")
        self.assertEqual(segment["duration_minutes"], 67)
        self.assertEqual(segment["evidence"]["lookup_status"], "verified")
        self.assertEqual(segment["evidence"]["source"], "12306-mcp:get-tickets")
        self.assertEqual(segment["fare"]["amount"], 91)
        self.assertEqual(segment["fare"]["seat_class"], "二等座")

    def test_to_route_segments_none(self):
        self.assertIsNone(to_route_segments(
            self.normalized, None, from_place_id="a", to_place_id="b",
            date="2026-11-10"))

    def test_session_payload(self):
        payload = session_payload(self.normalized)
        self.assertTrue(payload["verified"])
        self.assertEqual(payload["railway"]["leg_count"], 3)


class CliTests(unittest.TestCase):

    def test_cli_verified(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                         encoding="utf-8") as handle:
            handle.write(SAMPLE)
            path = handle.name
        try:
            out = os.path.join(tempfile.gettempdir(), "railway_cli_out.json")
            with open(out, "w", encoding="utf-8"):
                pass
            code = main(["--file", path, "--date", "2026-11-10",
                         "--from", "洛阳", "--to", "开封",
                         "--queried-at", "2026-11-05T19:00:00+08:00"])
            self.assertEqual(code, 0)
        finally:
            os.remove(path)

    def test_cli_no_result_returns_one(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                         encoding="utf-8") as handle:
            handle.write("未找到符合条件的车次")
            path = handle.name
        try:
            code = main(["--file", path, "--date", "2026-11-10",
                         "--from", "洛阳", "--to", "开封"])
            self.assertEqual(code, 1)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()