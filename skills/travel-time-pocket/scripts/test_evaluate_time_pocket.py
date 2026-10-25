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


if __name__ == "__main__":
    unittest.main()


