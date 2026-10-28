#!/usr/bin/env python3

import json
import unittest

from evaluate_time_pocket import evaluate_time_pocket, main


def request(candidate):
    return {
        "schema_version": "1.0",
        "current_time": "2026-11-01T16:00:00+08:00",
        "must_return_by": "2026-11-01T19:00:00+08:00",
        "origin": "甲秀楼",
        "return_to": "贵阳北站",
        "buffer_minutes": 25,
        "candidates": [candidate],
    }


def candidate():
    return {
        "id": "c1",
        "name": "博物馆",
        "travel_to_minutes": 20,
        "queue_minutes": 10,
        "minimum_visit_minutes": 60,
        "travel_back_minutes": 35,
        "available": True,
        "always_open": False,
        "opening_windows": [
            {"start": "2026-11-01T09:00:00+08:00", "end": "2026-11-01T18:00:00+08:00"}
        ],
    }


def verified_request(item=None):
    payload = request(item or candidate())
    payload.update(
        {
            "schema_version": "1.1",
            "departure_preparation_minutes": 10,
            "origin_place_id": "origin-1",
            "return_place_id": "return-1",
            "route_policy": {"require_status": True, "require_queried_at": True, "max_age_minutes": 30},
        }
    )
    target = payload["candidates"][0]
    target["place_id"] = "place-1"
    target.pop("travel_to_minutes", None)
    target.pop("travel_back_minutes", None)
    target["outbound_route"] = {
        "availability": "available",
        "duration_minutes": 20,
        "queried_at": "2026-11-01T15:55:00+08:00",
    }
    target["return_route"] = {
        "availability": "available",
        "duration_minutes": 35,
        "queried_at": "2026-11-01T15:56:00+08:00",
    }
    return payload


class EvaluateTimePocketTest(unittest.TestCase):
    def test_feasible_candidate_has_safe_return(self):
        report = evaluate_time_pocket(request(candidate()))
        self.assertEqual(report["status"], "feasible")
        self.assertEqual(report["candidates"][0]["safe_return_time"], "2026-11-01T18:30:00+08:00")
        self.assertEqual(report["candidates"][0]["spare_minutes"], 30)

    def test_candidate_that_misses_deadline_is_infeasible(self):
        item = candidate()
        item["minimum_visit_minutes"] = 120
        report = evaluate_time_pocket(request(item))
        self.assertEqual(report["status"], "infeasible")

    def test_wait_for_opening_is_counted(self):
        item = candidate()
        item["opening_windows"] = [
            {"start": "2026-11-01T17:00:00+08:00", "end": "2026-11-01T18:30:00+08:00"}
        ]
        report = evaluate_time_pocket(request(item))
        self.assertEqual(report["candidates"][0]["activity_start_time"], "2026-11-01T17:00:00+08:00")
        self.assertEqual(report["status"], "feasible")
        self.assertEqual(report["candidates"][0]["spare_minutes"], 0)

    def test_unknown_opening_is_incomplete(self):
        item = candidate()
        item["opening_windows"] = []
        report = evaluate_time_pocket(request(item))
        self.assertEqual(report["status"], "incomplete")

    def test_confirmed_unavailable_is_infeasible(self):
        item = candidate()
        item["available"] = False
        report = evaluate_time_pocket(request(item))
        self.assertEqual(report["status"], "infeasible")

    def test_agentarts_entry_point_returns_strings(self):
        output = main({"pocket_json": json.dumps(request(candidate()), ensure_ascii=False)})
        self.assertEqual(output["status"], "feasible")
        self.assertEqual(json.loads(output["report_json"])["status"], "feasible")

    def test_timezone_is_required(self):
        payload = request(candidate())
        payload["current_time"] = "2026-11-01T16:00:00"
        report = evaluate_time_pocket(payload)
        self.assertEqual(report["status"], "invalid")

    def test_preparation_time_is_counted(self):
        report = evaluate_time_pocket(verified_request())
        item = report["candidates"][0]
        self.assertEqual(report["status"], "feasible")
        self.assertEqual(item["departure_time"], "2026-11-01T16:10:00+08:00")
        self.assertEqual(item["safe_return_time"], "2026-11-01T18:40:00+08:00")
        self.assertEqual(item["duration_breakdown"]["total_after_departure_minutes"], 150)

    def test_unavailable_route_is_infeasible(self):
        payload = verified_request()
        payload["candidates"][0]["return_route"] = {"availability": "unavailable"}
        report = evaluate_time_pocket(payload)
        self.assertEqual(report["status"], "infeasible")
        self.assertIn("route_unavailable", report["candidates"][0]["reason_codes"])

    def test_unknown_route_is_incomplete(self):
        payload = verified_request()
        payload["candidates"][0]["outbound_route"] = {"availability": "unknown"}
        report = evaluate_time_pocket(payload)
        self.assertEqual(report["status"], "incomplete")
        self.assertIn("route_unknown", report["candidates"][0]["reason_codes"])

    def test_stale_route_data_is_incomplete(self):
        payload = verified_request()
        payload["candidates"][0]["outbound_route"]["queried_at"] = "2026-11-01T14:00:00+08:00"
        report = evaluate_time_pocket(payload)
        self.assertEqual(report["status"], "incomplete")
        self.assertIn("route_data_stale", report["candidates"][0]["reason_codes"])

    def test_missing_route_query_time_is_incomplete_in_schema_1_1(self):
        payload = verified_request()
        payload["candidates"][0]["outbound_route"].pop("queried_at")
        report = evaluate_time_pocket(payload)
        self.assertEqual(report["status"], "incomplete")
        self.assertIn("route_query_time_missing", report["candidates"][0]["reason_codes"])

    def test_zero_duration_between_distinct_places_is_incomplete(self):
        payload = verified_request()
        payload["candidates"][0]["outbound_route"]["duration_minutes"] = 0
        report = evaluate_time_pocket(payload)
        self.assertEqual(report["status"], "incomplete")
        self.assertIn("route_zero_duration_between_distinct_places", report["candidates"][0]["reason_codes"])

    def test_latest_entry_is_enforced(self):
        payload = verified_request()
        payload["candidates"][0]["latest_entry"] = "2026-11-01T16:20:00+08:00"
        report = evaluate_time_pocket(payload)
        self.assertEqual(report["status"], "infeasible")
        self.assertIn("latest_entry_missed", report["candidates"][0]["reason_codes"])

    def test_legacy_schema_remains_compatible(self):
        report = evaluate_time_pocket(request(candidate()))
        self.assertEqual(report["status"], "feasible")
        self.assertTrue(report["candidates"][0]["warnings"])

    def test_schema_1_1_does_not_treat_legacy_routes_as_verified(self):
        payload = request(candidate())
        payload["schema_version"] = "1.1"
        report = evaluate_time_pocket(payload)
        self.assertEqual(report["status"], "incomplete")
        self.assertIn("route_status_missing", report["candidates"][0]["reason_codes"])


if __name__ == "__main__":
    unittest.main()


