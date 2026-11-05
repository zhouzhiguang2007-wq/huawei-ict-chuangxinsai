import copy
import json
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from travel_shared.contracts import SKILLS, adapt_requirements, money_minor
from travel_shared.db import init_db
from travel_shared.seed_knowledge import seed_all
from travel_shared.server import make_server
from travel_shared.tools import TravelTools, main


ROOT = Path(__file__).resolve().parents[1]


def context(skill="travel-requirement-analysis", preferences=None, payload=None):
    return {"schema_version": "1.0", "trip_id": "demo-trip", "skill": skill,
            "requirements": {"destination": {"city": "贵阳"},
                             "dates": {"start_date": "2027-02-01", "days": 2},
                             "travelers": {"total": 2, "adults": 2},
                             "budget": {"amount": 3000, "currency": "CNY", "scope": "total_trip", "hard_limit": True},
                             "preferences": preferences or {}}, "payload": payload or {}}


class SharedToolsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "preferences.sqlite3"
        # prepare 现在会校验内部私有库是否已初始化（P0-3），测试用临时库需先 seed。
        self.internal_db = Path(self.temp.name) / "internal.sqlite3"
        init_db(str(self.internal_db))
        seed_all(str(self.internal_db))
        self.tools = TravelTools(self.db, internal_db_path=str(self.internal_db))

    def tearDown(self):
        self.temp.cleanup()

    def call(self, action, user="alice", **fields):
        return self.tools.handle({"action": action, **fields}, user_id=user)

    def save(self, prefs, user="alice"):
        return self.call("update", user, preferences=prefs, confirmed=True,
                         source="用户明确说：请记住这些长期偏好。")

    def test_persists_across_instances_and_isolates_users(self):
        self.assertEqual(self.save({"pace": "relaxed"})["status"], "ok")
        other = TravelTools(self.db)
        self.assertEqual(other.handle({"action": "get"}, user_id="alice")["data"]["preferences"],
                         {"pace": "relaxed"})
        self.assertEqual(self.call("get", "bob")["data"]["preferences"], {})

    def test_update_validates_atomically(self):
        self.save({"pace": "relaxed"})
        for prefs in ({"pace": "intensive", "budget": 100}, {"dates": "tomorrow"},
                      {"pace": "bad"}, {"walking_tolerance_minutes": True},
                      {"walking_tolerance_minutes": -1}, {"photo_styles": "film"},
                      {"transport_modes": ["teleport"]}, {"pace": None}):
            with self.subTest(prefs=prefs):
                self.assertEqual(self.save(prefs)["status"], "invalid")
        self.assertEqual(self.call("get")["data"]["preferences"], {"pace": "relaxed"})

    def test_unconfirmed_or_missing_evidence_cannot_write(self):
        for confirmed in (False, "true", 1, None):
            self.assertEqual(self.call("update", preferences={"pace": "relaxed"},
                                       confirmed=confirmed, source="user")["status"], "invalid")
        self.assertEqual(self.call("update", preferences={"pace": "relaxed"},
                                   confirmed=True, source="")["status"], "invalid")
        self.assertEqual(self.call("get")["data"]["preferences"], {})

    def test_delete_and_clear_are_scoped_and_idempotent(self):
        self.save({"pace": "relaxed", "interests": ["美食"]})
        self.save({"pace": "intensive"}, "bob")
        self.assertEqual(self.call("delete", fields=["pace"])["data"]["deleted_count"], 1)
        self.assertEqual(self.call("delete", fields=["pace"])["data"]["deleted_count"], 0)
        self.assertEqual(self.call("delete")["status"], "invalid")
        self.assertEqual(self.call("delete", fields=None)["status"], "invalid")
        self.call("clear")
        self.assertEqual(self.call("get")["data"]["preferences"], {})
        self.assertEqual(self.call("get", "bob")["data"]["preferences"]["pace"], "intensive")

    def test_current_over_trip_over_memory_without_writing(self):
        self.save({"pace": "relaxed", "interests": ["美食"], "photo_styles": ["胶片"]})
        ctx = context(preferences={"pace": "intensive", "interests": []})
        ctx["trip_preferences"] = {"pace": "balanced", "photo_styles": ["日系"]}
        original = copy.deepcopy(ctx)
        result = self.call("prepare", context=ctx)["data"]["context"]
        self.assertEqual(result["requirements"]["preferences"],
                         {"pace": "intensive", "interests": ["美食"], "photo_styles": ["日系"]})
        self.assertEqual(ctx, original)
        self.assertEqual(self.call("get")["data"]["preferences"]["pace"], "relaxed")

    def test_explicit_clear_and_unknown_defaults(self):
        self.save({"pace": "relaxed", "interests": ["美食"]})
        ctx = context(preferences={"pace": "unspecified", "interests": []})
        ctx["explicit_preference_fields"] = ["interests"]
        result = self.call("prepare", context=ctx)["data"]["context"]
        self.assertEqual(result["requirements"]["preferences"], {"pace": "relaxed", "interests": []})
        ctx["explicit_preference_fields"] = ["photo_styles"]
        self.assertEqual(self.call("prepare", context=ctx)["status"], "invalid")

    def test_snapshot_remains_consistent_across_skills(self):
        self.save({"pace": "relaxed"})
        ctx = self.call("prepare", context=context())["data"]["context"]
        self.save({"pace": "intensive"})
        for skill in SKILLS:
            with self.subTest(skill=skill):
                ctx["skill"] = skill
                result = self.call("prepare", context=ctx)
                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["data"]["context"]["requirements"]["preferences"]["pace"], "relaxed")

    def test_bad_snapshot_rejected(self):
        ctx = context()
        ctx["preference_snapshot"] = {"preferences": {"pace": "relaxed"},
                                      "origins": {}, "memory_status": "loaded"}
        self.assertEqual(self.call("prepare", context=ctx)["status"], "invalid")

    def test_changed_current_preferences_require_a_new_snapshot(self):
        ctx = self.call("prepare", context=context(preferences={"pace": "relaxed"}))["data"]["context"]
        ctx["requirements"]["preferences"] = {"pace": "intensive"}
        self.assertEqual(self.call("prepare", context=ctx)["status"], "invalid")
        ctx.pop("preference_snapshot")
        self.assertEqual(self.call("prepare", context=ctx)["status"], "ok")

    def test_openapi_and_manifest_match_runtime(self):
        spec = json.loads((ROOT / "contracts/tools.openapi.json").read_text(encoding="utf-8"))
        manifest = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(set(SKILLS), set(spec["components"]["schemas"]["Context"]["properties"]["skill"]["enum"]))
        self.assertEqual(set(SKILLS), set(manifest["skills"]))
        self.assertEqual(manifest["shared_tools"]["contract_version"], "1.1")
        for name in SKILLS:
            self.assertIn("shared-interface.md", (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8"))

    def test_malformed_empty_values_are_not_silently_treated_as_unknown(self):
        for field in ("preferences", "dates", "budget", "travelers", "destination"):
            ctx = context()
            ctx["requirements"][field] = []
            self.assertEqual(self.call("prepare", context=ctx)["status"], "invalid")

    def test_storage_failure_degrades_reads_but_reports_write_failure(self):
        with patch.object(self.tools.store, "get", side_effect=sqlite3.OperationalError("busy")):
            result = self.call("prepare", context=context(preferences={"pace": "balanced"}))
            self.assertEqual(result["status"], "ok")
            self.assertTrue(result["warnings"])
            self.assertEqual(result["data"]["context"]["preference_snapshot"]["memory_status"], "unavailable")
            self.assertEqual(self.call("get")["status"], "unavailable")
        with patch.object(self.tools.store, "update", side_effect=sqlite3.OperationalError("busy")):
            self.assertEqual(self.save({"pace": "relaxed"})["status"], "unavailable")

    def test_concurrent_field_updates_do_not_erase_each_other(self):
        prefs = [{"pace": "relaxed"}, {"interests": ["自然"]}, {"photo_styles": ["国风"]}]
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(self.save, prefs))
        self.assertTrue(all(r["status"] == "ok" for r in results))
        self.assertEqual(len(self.call("get")["data"]["preferences"]), 3)

    def test_parameterized_user_identity(self):
        self.save({"pace": "relaxed"}, "x' OR 1=1 --")
        self.assertEqual(self.call("get")["data"]["preferences"], {})
        self.assertEqual(self.call("get", "x' OR 1=1 --")["data"]["preferences"]["pace"], "relaxed")

    def test_identity_cannot_be_overridden_by_request(self):
        result = self.tools.handle({"action": "get", "user_id": "bob"}, user_id="alice")
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(self.tools.handle({"action": "get"}, user_id="")["status"], "invalid")

    def test_requirement_invoke_uses_merged_preferences(self):
        self.save({"pace": "relaxed", "photo_styles": ["胶片"]})
        result = self.call("invoke", context=context())
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["data"]["result"]["ready"])

    def test_memory_does_not_fill_trip_dates_or_budget(self):
        self.save({"pace": "relaxed"})
        ctx = context()
        ctx["requirements"]["dates"] = {}
        ctx["requirements"]["budget"] = None
        report = self.call("invoke", context=ctx)["data"]["result"]
        self.assertFalse(report["ready"])
        self.assertIn("dates.start_date", report["missing_fields"])
        self.assertIn("budget.amount", report["missing_fields"])

    def test_accommodation_mapping_does_not_invent_checkout_rooms_or_lodging_budget(self):
        result = self.call("prepare", context=context("travel-accommodation-advisor"))
        hints = result["data"]["input_hints"]
        self.assertIsNone(hints["check_out"])
        self.assertIsNone(hints["rooms"])
        self.assertNotIn("budget", hints)

    def test_money_precision_scope_and_soft_preferences(self):
        self.assertEqual(money_minor(12.34, "CNY"), 1234)
        self.assertEqual(money_minor(1234, "JPY"), 1234)
        for value, currency in ((1.001, "CNY"), (float("nan"), "CNY"), (True, "CNY"),
                                (-1, "CNY"), (10, "XXX")):
            with self.assertRaises(ValueError):
                money_minor(value, currency)
        req = context(preferences={"walking_tolerance_minutes": 45, "transport_modes": ["walk"]})["requirements"]
        mapping = adapt_requirements("travel-plan-review", req)["input_hints"]
        self.assertEqual(mapping["budget"]["amount_minor"], 300000)
        self.assertNotIn("daily_walking_limit_m", mapping)
        self.assertNotIn("allowed_transport_modes", mapping)
        req["budget"]["scope"] = "per_person"
        self.assertNotIn("budget", adapt_requirements("travel-plan-review", req)["input_hints"])
        req["budget"]["scope"] = "total_trip"
        req["budget"]["hard_limit"] = False
        self.assertNotIn("budget", adapt_requirements("travel-plan-review", req)["input_hints"])

    def test_native_review_status_is_preserved_and_budget_applied(self):
        plan = json.loads((ROOT / "skills/travel-plan-review/examples/basic-plan.json").read_text(encoding="utf-8"))
        # Fixture is a native payload, containing plan and optional as_of.
        ctx = context("travel-plan-review", payload=plan)
        ctx["requirements"]["budget"]["amount"] = 0
        result = self.call("invoke", context=ctx)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["result"]["status"], "fail")

    def test_other_native_tools_and_prepare_only_skills(self):
        for skill in ("multi-platform-travel-planner", "travel-time-pocket"):
            result = self.call("invoke", context=context(skill))
            self.assertEqual(result["status"], "ok")
            self.assertIn(result["data"]["result"]["status"], {"invalid", "incomplete"})
        result = self.call("invoke", context=context("travel-accommodation-advisor", payload={"offers": [], "budget": None}))
        self.assertEqual(result["status"], "ok")
        self.assertIn("status", result["data"]["result"])
        self.assertEqual(self.call("invoke", context=context("x-xiake"))["status"], "invalid")

    def test_agentarts_bridge(self):
        result = main({"request_json": json.dumps({"action": "get"})}, user_id="alice", db_path=self.db)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(json.loads(result["result_json"])["data"]["preferences"], {})
        self.assertEqual(main({"request_json": "bad"}, user_id="alice", db_path=self.db)["status"], "invalid")

    def test_bad_contracts_return_invalid(self):
        for request in (None, [], {"action": "bad"}, {"action": "prepare", "context": {}},
                        {"action": "prepare", "context": {**context(), "schema_version": "2"}},
                        {"action": "prepare", "context": {**context(), "skill": "other"}}):
            self.assertEqual(self.tools.handle(request, user_id="alice")["status"], "invalid")


class HTTPTest(unittest.TestCase):
    def test_identity_authentication_and_json_interface(self):
        with tempfile.TemporaryDirectory() as temp:
            server = make_server(("127.0.0.1", 0), TravelTools(Path(temp) / "test.sqlite3"),
                                 {"alice-secret": "alice", "bob-secret": "bob"})
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = "http://127.0.0.1:%s/v1/tools" % server.server_address[1]

            def post(body, token):
                req = Request(url, data=json.dumps(body).encode(),
                              headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
                return json.load(urlopen(req, timeout=5))

            try:
                with self.assertRaises(HTTPError) as error:
                    post({"action": "get"}, "wrong")
                self.assertEqual(error.exception.code, 401)
                post({"action": "update", "preferences": {"pace": "relaxed"},
                      "confirmed": True, "source": "user confirmation"}, "alice-secret")
                self.assertEqual(post({"action": "get"}, "bob-secret")["data"]["preferences"], {})
                self.assertEqual(post({"action": "get"}, "alice-secret")["data"]["preferences"]["pace"], "relaxed")
                with self.assertRaises(HTTPError) as error:
                    post({"action": "get", "user_id": "alice"}, "bob-secret")
                self.assertEqual(error.exception.code, 400)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
