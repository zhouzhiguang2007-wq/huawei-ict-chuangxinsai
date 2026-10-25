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

    def test_unknown_budget_is_warning_not_core_blocker(self):
        request = complete_request()
        request["budget"]["amount"] = None
        result = validate_requirements(request)
        self.assertTrue(result["valid"])
        self.assertTrue(result["ready"])
        self.assertTrue(result["warnings"])


if __name__ == "__main__":
    unittest.main()


