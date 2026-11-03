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
            "confirmed_by_user": True,
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
        request["location_resolution"] = {
            "status": "confirmed",
            "confirmed_by_user": True,
            "departure_poi_id": "test-poi",
            "return_poi_id": None,
            "ambiguous_fields": [],
        }
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

    # --- 地点歧义场景测试（通用机制，不针对单一例子写特判） ---

    def _confirm_departure(self, request, poi_id="poi-1", source="user_pick"):
        request["location_resolution"] = {
            "status": "confirmed",
            "confirmed_by_user": True,
            "departure_poi_id": poi_id,
            "return_poi_id": None,
            "ambiguous_fields": [],
            "confirmation_source": source,
        }
        request["dates"]["departure_availability"] = {"status": "flexible", "earliest": None, "latest": None}
        return request

    def test_city_only_departure_is_ambiguous_for_door_to_door(self):
        # 用户只说"福州"：城市级位置，不能据此计算门到门接驳时间。
        request = complete_request()
        request["departure_location"] = "福州"
        request["time_plan_required"] = True
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

    def test_multi_campus_university_ambiguous_blocks_ready(self):
        # 福建农林大学多校区，未确认具体校区。
        request = complete_request()
        request["departure_location"] = "福建农林大学"
        request["location_resolution"] = {
            "status": "ambiguous",
            "departure_poi_id": None,
            "return_poi_id": None,
            "ambiguous_fields": ["departure_location.detail"],
        }
        result = validate_requirements(request)
        self.assertFalse(result["ready"])
        self.assertIn("departure_location.detail", result["missing_fields"])

    def test_multi_hospital_sites_ambiguous_blocks_ready(self):
        # 某医院多院区，未确认具体院区。
        request = complete_request()
        request["departure_location"] = "某市第一医院"
        request["location_resolution"] = {
            "status": "ambiguous",
            "departure_poi_id": None,
            "return_poi_id": None,
            "ambiguous_fields": ["departure_location.detail"],
        }
        result = validate_requirements(request)
        self.assertFalse(result["ready"])
        self.assertIn("departure_location.detail", result["missing_fields"])

    def test_unique_address_confirmed_via_confirmation_source(self):
        # 唯一明确地址，confirmed 但无 POI ID，靠 confirmation_source 也可。
        request = complete_request()
        request["departure_location"] = "福州市鼓楼区XX路1号"
        self._confirm_departure(request, poi_id=None, source="user_typed_full_address")
        result = validate_requirements(request)
        self.assertTrue(result["valid"], result["errors"])
        self.assertTrue(result["ready"], result["missing_fields"])

    def test_confirmed_without_poi_or_source_is_invalid(self):
        # 防谎报：confirmed 但既无 POI ID 也无 confirmation_source → invalid。
        request = complete_request()
        request["departure_location"] = "福建农林大学"
        request["location_resolution"] = {
            "status": "confirmed",
            "confirmed_by_user": True,
            "departure_poi_id": None,
            "return_poi_id": None,
            "ambiguous_fields": [],
        }
        result = validate_requirements(request)
        self.assertFalse(result["valid"])
        self.assertTrue(any("confirmation_source" in e for e in result["errors"]))

    def test_user_confirmed_specific_campus_then_ready(self):
        # 用户确认具体校区后，保存 POI ID 与确认来源，ready。
        request = complete_request()
        request["departure_location"] = "福建农林大学大学城校区"
        self._confirm_departure(request, poi_id="B0FFFAFJXX", source="user_pick_from_candidates")
        result = validate_requirements(request)
        self.assertTrue(result["valid"], result["errors"])
        self.assertTrue(result["ready"], result["missing_fields"])

    def test_user_changes_departure_resets_to_ambiguous(self):
        # 用户后来更改出发地，未重新确认 → 重新 ambiguous，不复用旧 confirmed。
        request = complete_request()
        request["departure_location"] = "福建农林大学大学城校区"
        self._confirm_departure(request, poi_id="B0FFFAFJXX", source="user_pick_from_candidates")
        self.assertTrue(validate_requirements(request)["ready"])

        request["departure_location"] = "福州站"  # 同名车站可能有多个入口/广场
        request["location_resolution"] = {
            "status": "ambiguous",
            "departure_poi_id": None,
            "return_poi_id": None,
            "ambiguous_fields": ["departure_location.detail"],
            "confirmation_source": None,
        }
        result = validate_requirements(request)
        self.assertFalse(result["ready"])
        self.assertIn("departure_location.detail", result["missing_fields"])

    def test_city_level_research_allowed_without_time_plan(self):
        # 不需要精确时间规划时，城市级出发地不阻断（可继续城市级研究）。
        request = complete_request()
        request["departure_location"] = "福州"
        request["time_plan_required"] = False
        request["location_resolution"] = {
            "status": "unknown",
            "departure_poi_id": None,
            "return_poi_id": None,
            "ambiguous_fields": [],
        }
        result = validate_requirements(request)
        self.assertTrue(result["valid"])
        self.assertTrue(result["ready"])

    # --- confirmed_by_user 硬门禁：防止把搜索首条/主校区/分店静默当成用户确认 ---

    def test_confirmed_by_user_true_while_ambiguous_is_invalid(self):
        # 未确认（ambiguous）却置 confirmed_by_user=true → invalid。
        request = complete_request()
        request["departure_location"] = "福建农林大学"
        request["location_resolution"] = {
            "status": "ambiguous",
            "confirmed_by_user": True,
            "departure_poi_id": None,
            "return_poi_id": None,
            "ambiguous_fields": ["departure_location.detail"],
        }
        result = validate_requirements(request)
        self.assertFalse(result["valid"])
        self.assertTrue(any("confirmed_by_user" in e for e in result["errors"]))

    def test_confirmed_requires_confirmed_by_user_true(self):
        # status=confirmed 但 confirmed_by_user 为 False/缺失 → invalid。
        request = complete_request()
        request["departure_location"] = "福建农林大学大学城校区"
        request["location_resolution"] = {
            "status": "confirmed",
            "confirmed_by_user": False,
            "departure_poi_id": "B0FFFAFJXX",
            "return_poi_id": None,
            "ambiguous_fields": [],
            "confirmation_source": "user_pick",
        }
        result = validate_requirements(request)
        self.assertFalse(result["valid"])
        self.assertTrue(any("confirmed_by_user" in e for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()


