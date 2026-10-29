"""Offline regression tests for the complete-route checker."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from validate_route_timeline import validate_route


def sample_route():
    return {
        "trip": {
            "start_date": "2026-10-30",
            "end_date": "2026-10-31",
            "days": 2,
            "start_place_id": "luoyang-meeting",
            "end_place_id": "luoyang-dropoff",
        },
        "daily_routes": [
            {
                "date": "2026-10-30",
                "start_anchor": {"at": "2026-10-30T08:00+08:00", "place_id": "luoyang-meeting"},
                "end_anchor": {"at": "2026-10-30T14:45+08:00", "place_id": "hotel"},
                "segments": [
                    {"id": "gather", "kind": "gather", "start": "2026-10-30T08:00+08:00",
                     "end": "2026-10-30T08:15+08:00", "place_id": "luoyang-meeting"},
                    {"id": "outbound", "kind": "transfer", "start": "2026-10-30T08:15+08:00",
                     "end": "2026-10-30T11:45+08:00", "from_place_id": "luoyang-meeting",
                     "to_place_id": "attraction", "mode": "coach"},
                    {"id": "visit-a", "kind": "visit", "start": "2026-10-30T11:45+08:00",
                     "end": "2026-10-30T13:45+08:00", "place_id": "attraction",
                     "visit_minutes": 120, "highlights": ["虹桥", "宋代街市"]},
                    {"id": "hotel-leg", "kind": "transfer", "start": "2026-10-30T13:45+08:00",
                     "end": "2026-10-30T14:00+08:00", "from_place_id": "attraction",
                     "to_place_id": "hotel", "mode": "coach"},
                    {"id": "meal-a", "kind": "meal", "start": "2026-10-30T14:00+08:00",
                     "end": "2026-10-30T14:45+08:00", "place_id": "hotel"},
                ],
            },
            {
                "date": "2026-10-31",
                "start_anchor": {"at": "2026-10-31T08:00+08:00", "place_id": "hotel"},
                "end_anchor": {"at": "2026-10-31T15:00+08:00", "place_id": "luoyang-dropoff"},
                "segments": [
                    {"id": "breakfast", "kind": "meal", "start": "2026-10-31T08:00+08:00",
                     "end": "2026-10-31T08:30+08:00", "place_id": "hotel"},
                    {"id": "museum-leg", "kind": "transfer", "start": "2026-10-31T08:30+08:00",
                     "end": "2026-10-31T09:00+08:00", "from_place_id": "hotel",
                     "to_place_id": "museum", "mode": "coach"},
                    {"id": "visit-b", "kind": "visit", "start": "2026-10-31T09:00+08:00",
                     "end": "2026-10-31T11:00+08:00", "place_id": "museum",
                     "visit_minutes": 120, "highlights": ["馆藏书画", "宋代城市展"]},
                    {"id": "meal-b", "kind": "meal", "start": "2026-10-31T11:00+08:00",
                     "end": "2026-10-31T12:00+08:00", "place_id": "museum"},
                    {"id": "return", "kind": "transfer", "start": "2026-10-31T12:00+08:00",
                     "end": "2026-10-31T15:00+08:00", "from_place_id": "museum",
                     "to_place_id": "luoyang-dropoff", "mode": "coach"},
                ],
            },
        ],
    }


def rules(report, status):
    return {item["rule"] for item in report["checks"] if item["status"] == status}


class RouteTimelineTests(unittest.TestCase):
    def setUp(self):
        self.route = sample_route()

    def assert_rule(self, expected_status, expected_rule):
        result = validate_route(self.route)
        self.assertEqual(result["status"], expected_status, result)
        self.assertIn(expected_rule, rules(result, "unknown" if expected_status == "incomplete" else "fail"))

    def test_complete_two_day_route_passes(self):
        result = validate_route(self.route)
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["summary"]["failed"], 0)

    def test_missing_travel_day_fails(self):
        self.route["daily_routes"].pop()
        self.assert_rule("fail", "expected_day")

    def test_unknown_route_list_is_incomplete(self):
        self.route["daily_routes"] = None
        self.assert_rule("incomplete", "missing_data")

    def test_unknown_day_label_is_incomplete(self):
        self.route["daily_routes"][1]["date"] = None
        self.assert_rule("incomplete", "expected_day")

    def test_mismatched_day_count_fails(self):
        self.route["trip"]["days"] = 3
        self.assert_rule("fail", "trip_days")

    def test_unconnected_adjacent_places_fail(self):
        self.route["daily_routes"][0]["segments"][1]["to_place_id"] = "wrong-place"
        self.assert_rule("fail", "place_continuity")

    def test_unconnected_overnight_place_fails(self):
        route = self.route["daily_routes"][1]
        route["start_anchor"]["place_id"] = "other-hotel"
        route["segments"][0]["place_id"] = "other-hotel"
        route["segments"][1]["from_place_id"] = "other-hotel"
        self.assert_rule("fail", "overnight_place")

    def test_next_day_cannot_start_before_previous_ends(self):
        route = self.route["daily_routes"][0]
        route["segments"][-1]["end"] = "2026-10-31T09:00+08:00"
        route["end_anchor"]["at"] = "2026-10-31T09:00+08:00"
        self.assert_rule("fail", "overnight_time")

    def test_overlapping_segments_fail(self):
        self.route["daily_routes"][0]["segments"][1]["start"] = "2026-10-30T08:10+08:00"
        self.assert_rule("fail", "time_overlap")

    def test_single_long_unexplained_gap_fails(self):
        self.route["daily_routes"][0]["segments"][1]["start"] = "2026-10-30T09:15+08:00"
        self.assert_rule("fail", "unexplained_gap")

    def test_cumulative_small_gaps_fail(self):
        route = self.route["daily_routes"][0]
        segments = route["segments"]
        segments[1]["start"] = "2026-10-30T08:50+08:00"
        segments[2]["start"] = "2026-10-30T12:20+08:00"
        segments[2]["end"] = "2026-10-30T14:20+08:00"
        segments[3]["start"] = "2026-10-30T14:20+08:00"
        segments[3]["end"] = "2026-10-30T14:35+08:00"
        segments[4]["start"] = "2026-10-30T14:35+08:00"
        segments[4]["end"] = "2026-10-30T15:20+08:00"
        route["end_anchor"]["at"] = "2026-10-30T15:20+08:00"
        self.assert_rule("fail", "daily_unexplained_gap")

    def test_explicit_rest_accounts_for_gap(self):
        route = self.route["daily_routes"][0]
        route["segments"][1]["start"] = "2026-10-30T09:15+08:00"
        route["segments"].insert(1, {
            "id": "rest-at-meeting", "kind": "rest", "start": "2026-10-30T08:15+08:00",
            "end": "2026-10-30T09:15+08:00", "place_id": "luoyang-meeting"})
        self.assertEqual(validate_route(self.route)["status"], "pass")

    def test_first_day_must_begin_at_trip_origin(self):
        self.route["trip"]["start_place_id"] = "different-station"
        self.assert_rule("fail", "trip_start_place")

    def test_last_day_must_end_at_trip_destination(self):
        self.route["trip"]["end_place_id"] = "different-station"
        self.assert_rule("fail", "trip_end_place")

    def test_anchor_must_touch_first_segment(self):
        self.route["daily_routes"][0]["start_anchor"]["at"] = "2026-10-30T07:45+08:00"
        self.assert_rule("fail", "start_anchor_time")

    def test_visit_duration_claim_must_match_times(self):
        self.route["daily_routes"][0]["segments"][2]["visit_minutes"] = 90
        self.assert_rule("fail", "visit_minutes")

    def test_two_distinct_highlights_required(self):
        self.route["daily_routes"][0]["segments"][2]["highlights"] = ["虹桥", "虹桥"]
        self.assert_rule("fail", "visit_highlights")

    def test_unrecognized_segment_kind_cannot_bypass_visit_details(self):
        self.route["daily_routes"][0]["segments"][2]["kind"] = "sightseeing"
        self.assertEqual(validate_route(self.route)["status"], "invalid")

    def test_unknown_highlights_are_incomplete(self):
        self.route["daily_routes"][0]["segments"][2]["highlights"] = None
        self.assert_rule("incomplete", "missing_data")

    def test_unknown_transfer_mode_is_incomplete(self):
        self.route["daily_routes"][0]["segments"][1]["mode"] = None
        self.assert_rule("incomplete", "missing_data")

    def test_unknown_time_is_incomplete(self):
        self.route["daily_routes"][1]["segments"][2]["start"] = None
        self.assert_rule("incomplete", "missing_data")

    def test_missing_segments_are_incomplete(self):
        self.route["daily_routes"][0]["segments"] = []
        self.assert_rule("incomplete", "route_coverage")

    def test_timezone_is_required(self):
        self.route["daily_routes"][0]["segments"][0]["start"] = "2026-10-30T08:00"
        result = validate_route(self.route)
        self.assertEqual(result["status"], "invalid")

    def test_invalid_integer_type_is_rejected(self):
        self.route["daily_routes"][0]["segments"][2]["visit_minutes"] = True
        self.assertEqual(validate_route(self.route)["status"], "invalid")

    def test_reversed_days_fail(self):
        self.route["daily_routes"].reverse()
        self.assert_rule("fail", "date_order")

    def test_cross_midnight_and_next_day_anchor(self):
        route = self.route["daily_routes"][0]
        route["segments"][-1]["end"] = "2026-10-31T00:30+08:00"
        route["end_anchor"]["at"] = "2026-10-31T00:30+08:00"
        next_route = self.route["daily_routes"][1]
        next_route["start_anchor"]["at"] = "2026-10-31T01:00+08:00"
        next_route["segments"][0]["start"] = "2026-10-31T01:00+08:00"
        self.assertEqual(validate_route(self.route)["status"], "pass")

    def test_cli_reads_stdin(self):
        script = Path(__file__).with_name("validate_route_timeline.py")
        result = subprocess.run([sys.executable, str(script)], input=json.dumps(self.route),
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "pass")


if __name__ == "__main__":
    unittest.main()
