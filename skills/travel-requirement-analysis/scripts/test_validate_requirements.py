#!/usr/bin/env python3

import unittest

from validate_requirements import validate_requirements


def complete_request():
    return {
        "schema_version": "1.0",
        "destination": {"city": "贵阳", "areas": [], "must_visit": [], "avoid": []},
        "dates": {"start_date": "2026-11-01", "end_date": "2026-11-03", "days": 3, "flexible": False, "time_windows": []},
        "travelers": {"total": 3, "adults": 2, "children": 1, "older_adults": 0, "mobility_needs": []},
        "budget": {"amount": 3000, "currency": "CNY", "scope": "total_trip", "hard_limit": True},
        "preferences": {"interests": [], "pace": "balanced", "transport_modes": ["walk", "transit"], "walking_tolerance_minutes": 45, "accommodation": []},
        "constraints": [],
        "departure_location": None,
        "return_location": None,
        "unknown_fields": [],
        "derived_fields": [],
        "source_notes": [],
    }


class ValidateRequirementsTest(unittest.TestCase):
    def test_complete_request_is_ready(self):
        result = validate_requirements(complete_request())
        self.assertTrue(result["valid"])
        self.assertTrue(result["ready"])

    def test_missing_core_fields_needs_clarification(self):
        request = complete_request()
        request["destination"]["city"] = None
        request["dates"]["start_date"] = None
        result = validate_requirements(request)
        self.assertTrue(result["valid"])
        self.assertFalse(result["ready"])
        self.assertEqual(result["missing_fields"], ["destination.city", "dates.start_date"])

    def test_date_and_days_conflict_is_invalid(self):
        request = complete_request()
        request["dates"]["days"] = 2
        result = validate_requirements(request)
        self.assertFalse(result["valid"])
        self.assertIn("dates.days conflicts with inclusive start/end dates", result["errors"])

    def test_traveler_breakdown_conflict_is_invalid(self):
        request = complete_request()
        request["travelers"]["total"] = 4
        result = validate_requirements(request)
        self.assertFalse(result["valid"])

    def test_unknown_budget_blocks_full_trip(self):
        request = complete_request()
        request["budget"]["amount"] = None
        result = validate_requirements(request)
        self.assertTrue(result["valid"])
        self.assertFalse(result["ready"])
        self.assertIn("budget.amount", result["missing_fields"])
        self.assertTrue(result["warnings"])

    def test_unknown_days_blocks_full_trip_without_guessing(self):
        request = complete_request()
        request["dates"]["days"] = None
        request["dates"]["end_date"] = None
        result = validate_requirements(request)
        self.assertTrue(result["valid"])
        self.assertFalse(result["ready"])
        self.assertIn("dates.days", result["missing_fields"])

    def test_existing_budget_and_group_size_are_reused(self):
        request = complete_request()
        request["dates"]["start_date"] = None
        request["dates"]["end_date"] = None
        result = validate_requirements(request)
        self.assertEqual(result["missing_fields"], ["dates.start_date"])

    def test_ambiguous_origin_blocks_door_to_door_plan(self):
        request = complete_request()
        request["departure_location"] = "福建农林大学"
        request["location_resolution"] = {
            "status": "ambiguous",
            "departure_poi_id": None,
            "return_poi_id": None,
            "ambiguous_fields": ["departure_location.detail"],
        }
        result = validate_requirements(request)
        self.assertTrue(result["valid"])
        self.assertFalse(result["ready"])
        self.assertIn("departure_location.detail", result["missing_fields"])

        request["departure_location"] = "用户确认的具体校区"
        request["location_resolution"] = {
            "status": "confirmed",
            "departure_poi_id": "test-poi",
            "return_poi_id": None,
            "ambiguous_fields": [],
        }
        request["dates"]["departure_availability"] = {"status": "flexible", "earliest": None, "latest": None}
        self.assertTrue(validate_requirements(request)["ready"])

    def test_ambiguous_return_branch_is_generic(self):
        request = complete_request()
        request["return_location"] = "某连锁酒店"
        request["location_resolution"] = {
            "status": "ambiguous",
            "departure_poi_id": None,
            "return_poi_id": None,
            "ambiguous_fields": ["return_location.detail"],
        }
        result = validate_requirements(request)
        self.assertTrue(result["valid"])
        self.assertFalse(result["ready"])
        self.assertIn("return_location.detail", result["missing_fields"])

    def test_date_only_does_not_imply_all_day_departure(self):
        request = complete_request()
        request["departure_location"] = "用户确认的具体出发地"
        request["dates"]["departure_availability"] = {"status": "unknown", "earliest": None, "latest": None}
        result = validate_requirements(request)
        self.assertTrue(result["valid"])
        self.assertTrue(result["ready"])
        self.assertTrue(any("departure availability" in warning for warning in result["warnings"]))

        request["time_plan_required"] = True
        result = validate_requirements(request)
        self.assertFalse(result["ready"])
        self.assertIn("dates.departure_availability", result["missing_fields"])

        request["dates"]["departure_availability"] = {"status": "window", "earliest": "13:00", "latest": None}
        self.assertTrue(validate_requirements(request)["ready"])
        request["dates"]["departure_availability"] = {"status": "flexible", "earliest": None, "latest": None}
        self.assertTrue(validate_requirements(request)["ready"])

    def test_inspiration_request_does_not_require_departure_time(self):
        request = complete_request()
        request["departure_location"] = "某城市"
        request["time_plan_required"] = False
        self.assertTrue(validate_requirements(request)["ready"])

    def test_departure_window_requires_valid_time(self):
        request = complete_request()
        request["departure_location"] = "用户确认的具体出发地"
        request["dates"]["departure_availability"] = {"status": "window", "earliest": "25:00", "latest": None}
        self.assertFalse(validate_requirements(request)["valid"])


if __name__ == "__main__":
    unittest.main()


