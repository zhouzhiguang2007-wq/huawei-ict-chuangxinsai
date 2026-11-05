"""Tests for the internal private database modules (A/B/C).

Pure unittest style (no pytest dependency) so CI's
`python -m unittest discover -s tests` collects and runs them on
Python 3.9 / 3.13 without extra packages.

Tests cover:
  - db.py: schema initialization
  - knowledge.py (Module A): query, upsert, bulk_upsert, categories, delete
  - session.py (Module B): put, get, get_requirements, list_trips, clear
  - registry.py (Module C): get, list_all, match, upsert, dependencies
  - seed_knowledge.py: seed_all populates all tables
  - tools.py: new actions wired correctly
"""

import tempfile
import unittest
from pathlib import Path

from travel_shared.db import get_connection, init_db
from travel_shared.knowledge import KnowledgeStore
from travel_shared.session import SessionStore
from travel_shared.registry import SkillRegistry
from travel_shared.seed_knowledge import seed_all, SKILL_REGISTRY_DATA
from travel_shared.tools import TravelTools


class InternalDBTestCase(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.tmp_db = str(Path(self._tmpdir) / "test_internal.sqlite3")
        init_db(self.tmp_db)
        self.seeded_db = str(Path(self._tmpdir) / "test_seeded.sqlite3")
        init_db(self.seeded_db)
        seed_all(self.seeded_db)


# ===== db.py tests =====

class TestDB(InternalDBTestCase):

    def test_init_creates_tables(self):
        conn = get_connection(self.tmp_db)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        self.assertIn("travel_knowledge", tables)
        self.assertIn("session_context", tables)
        self.assertIn("skill_registry", tables)

    def test_init_creates_indexes(self):
        conn = get_connection(self.tmp_db)
        indexes = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()}
        conn.close()
        self.assertIn("idx_knowledge_category", indexes)
        self.assertIn("idx_session_trip", indexes)
        self.assertIn("idx_session_skill", indexes)

    def test_idempotent_init(self):
        init_db(self.tmp_db)
        init_db(self.tmp_db)
        conn = get_connection(self.tmp_db)
        count = conn.execute("SELECT COUNT(*) FROM travel_knowledge").fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)


# ===== Module A: KnowledgeStore tests =====

class TestKnowledgeStore(InternalDBTestCase):

    def test_upsert_and_query_exact(self):
        ks = KnowledgeStore(self.tmp_db)
        ks.upsert("city_info", "测试城市",
                  {"province": "测试省", "known_spots": ["景点A"]})
        result = ks.query(category="city_info", key="测试城市")
        self.assertTrue(result["found"])
        self.assertEqual(result["value"]["province"], "测试省")
        self.assertEqual(result["value"]["known_spots"], ["景点A"])

    def test_query_not_found(self):
        ks = KnowledgeStore(self.tmp_db)
        result = ks.query(category="city_info", key="不存在")
        self.assertFalse(result["found"])

    def test_query_by_category(self):
        ks = KnowledgeStore(self.tmp_db)
        ks.upsert("city_info", "城市A", {"spots": ["a"]})
        ks.upsert("city_info", "城市B", {"spots": ["b"]})
        ks.upsert("budget_reference", "经济型", {"range": "100-300"})
        result = ks.query(category="city_info")
        self.assertTrue(result["found"])
        self.assertEqual(len(result["results"]), 2)

    def test_query_by_keyword(self):
        ks = KnowledgeStore(self.tmp_db)
        ks.upsert("city_info", "贵阳", {"known_spots": ["甲秀楼"]})
        ks.upsert("local_food", "贵州", {"signature_dishes": ["酸汤鱼"]})
        result = ks.query(keyword="贵阳")
        self.assertTrue(result["found"])
        self.assertGreaterEqual(len(result["results"]), 1)

    def test_bulk_upsert(self):
        ks = KnowledgeStore(self.tmp_db)
        entries = [
            {"category": "city_info", "key": "城市C", "value": {"spots": ["c"]}},
            {"category": "city_info", "key": "城市D", "value": {"spots": ["d"]}},
        ]
        result = ks.bulk_upsert(entries)
        self.assertEqual(result["count"], 2)
        self.assertTrue(ks.query(category="city_info", key="城市C")["found"])
        self.assertTrue(ks.query(category="city_info", key="城市D")["found"])

    def test_upsert_overwrites(self):
        ks = KnowledgeStore(self.tmp_db)
        ks.upsert("city_info", "城市E", {"v": 1})
        ks.upsert("city_info", "城市E", {"v": 2})
        result = ks.query(category="city_info", key="城市E")
        self.assertEqual(result["value"]["v"], 2)

    def test_categories(self):
        ks = KnowledgeStore(self.tmp_db)
        ks.upsert("city_info", "A", {})
        ks.upsert("budget_reference", "B", {})
        cats = ks.categories()
        names = [c["name"] for c in cats["categories"]]
        self.assertIn("city_info", names)
        self.assertIn("budget_reference", names)

    def test_delete(self):
        ks = KnowledgeStore(self.tmp_db)
        ks.upsert("city_info", "ToDelete", {"v": 1})
        result = ks.delete("city_info", "ToDelete")
        self.assertEqual(result["deleted"], 1)
        self.assertFalse(ks.query(category="city_info", key="ToDelete")["found"])


# ===== Module B: SessionStore tests =====

class TestSessionStore(InternalDBTestCase):

    def test_put_and_get(self):
        ss = SessionStore(self.tmp_db)
        ss.put("trip_001", "travel-requirement-analysis", "confirmed",
               "requirements", {"city": "贵阳", "days": 3})
        result = ss.get("trip_001")
        self.assertEqual(result["count"], 1)
        entry = result["entries"][0]
        self.assertEqual(entry["skill"], "travel-requirement-analysis")
        self.assertEqual(entry["stage"], "confirmed")
        self.assertEqual(entry["key"], "requirements")
        self.assertEqual(entry["value"]["city"], "贵阳")

    def test_put_overwrites(self):
        ss = SessionStore(self.tmp_db)
        ss.put("trip_001", "travel-requirement-analysis", "confirmed",
               "requirements", {"city": "贵阳"})
        ss.put("trip_001", "travel-requirement-analysis", "confirmed",
               "requirements", {"city": "开封"})
        result = ss.get("trip_001")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["entries"][0]["value"]["city"], "开封")

    def test_get_filtered_by_skill(self):
        ss = SessionStore(self.tmp_db)
        ss.put("trip_001", "travel-requirement-analysis", "confirmed",
               "requirements", {"city": "贵阳"})
        ss.put("trip_001", "multi-platform-travel-planner", "candidate",
               "spots", ["甲秀楼", "黔灵山"])
        result = ss.get("trip_001", skill="travel-requirement-analysis")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["entries"][0]["key"], "requirements")

    def test_get_filtered_by_stage(self):
        ss = SessionStore(self.tmp_db)
        ss.put("trip_001", "multi-platform-travel-planner", "candidate",
               "spots", ["甲秀楼"])
        ss.put("trip_001", "multi-platform-travel-planner", "verified",
               "weather", {"sunny": True})
        result = ss.get("trip_001", skill="multi-platform-travel-planner",
                        stage="candidate")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["entries"][0]["key"], "spots")

    def test_get_requirements(self):
        ss = SessionStore(self.tmp_db)
        ss.put("trip_001", "travel-requirement-analysis", "confirmed",
               "requirements", {"city": "贵阳", "days": 3, "budget": 3000})
        result = ss.get_requirements("trip_001")
        self.assertTrue(result["found"])
        self.assertEqual(result["requirements"]["city"], "贵阳")
        self.assertEqual(result["requirements"]["days"], 3)

    def test_get_requirements_not_found(self):
        ss = SessionStore(self.tmp_db)
        result = ss.get_requirements("trip_999")
        self.assertFalse(result["found"])

    def test_list_trips(self):
        ss = SessionStore(self.tmp_db)
        ss.put("trip_A", "travel-requirement-analysis", "confirmed", "k", "v")
        ss.put("trip_B", "travel-requirement-analysis", "confirmed", "k", "v")
        result = ss.list_trips()
        self.assertIn("trip_A", result["trips"])
        self.assertIn("trip_B", result["trips"])

    def test_clear_trip(self):
        ss = SessionStore(self.tmp_db)
        ss.put("trip_001", "travel-requirement-analysis", "confirmed", "k", "v")
        ss.put("trip_001", "multi-platform-travel-planner", "candidate", "k2", "v2")
        result = ss.clear_trip("trip_001")
        self.assertEqual(result["deleted"], 2)
        self.assertEqual(ss.get("trip_001")["count"], 0)

    def test_clear_stage(self):
        ss = SessionStore(self.tmp_db)
        ss.put("trip_001", "travel-requirement-analysis", "confirmed", "k", "v")
        ss.put("trip_001", "travel-requirement-analysis", "candidate", "k2", "v2")
        result = ss.clear_stage("trip_001", "travel-requirement-analysis", "confirmed")
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(ss.get("trip_001")["count"], 1)


# ===== Module C: SkillRegistry tests =====

class TestSkillRegistry(InternalDBTestCase):

    def test_upsert_and_get(self):
        sr = SkillRegistry(self.tmp_db)
        sr.upsert("test-skill", "测试技能", "analysis",
                  ["测试", "技能"], "这是一个测试技能",
                  ["dep1"], "输出测试结果")
        result = sr.get("test-skill")
        self.assertTrue(result["found"])
        self.assertEqual(result["display_name"], "测试技能")
        self.assertEqual(result["trigger_keywords"], ["测试", "技能"])
        self.assertEqual(result["dependencies"], ["dep1"])

    def test_get_not_found(self):
        sr = SkillRegistry(self.tmp_db)
        result = sr.get("nonexistent")
        self.assertFalse(result["found"])

    def test_list_all(self):
        sr = SkillRegistry(self.tmp_db)
        sr.upsert("skill-a", "技能A", "analysis", ["a"], "desc a")
        sr.upsert("skill-b", "技能B", "planning", ["b"], "desc b")
        result = sr.list_all()
        self.assertEqual(result["count"], 2)

    def test_match_by_keyword(self):
        sr = SkillRegistry(self.tmp_db)
        sr.upsert("photo-skill", "拍照技能", "photo",
                  ["拍照", "出片", "机位"], "拍照指导")
        sr.upsert("food-skill", "美食技能", "planning",
                  ["美食", "吃"], "美食推荐")
        result = sr.match("我想拍照出片")
        self.assertGreaterEqual(result["count"], 1)
        self.assertEqual(result["matched_skills"][0]["skill_name"], "photo-skill")

    def test_match_no_results(self):
        sr = SkillRegistry(self.tmp_db)
        sr.upsert("skill-a", "技能A", "analysis", ["a"], "desc a")
        result = sr.match("完全不匹配的查询")
        self.assertEqual(result["count"], 0)

    def test_bulk_upsert(self):
        sr = SkillRegistry(self.tmp_db)
        entries = [
            {"skill_name": "skill-1", "display_name": "技能1", "category": "analysis",
             "trigger_keywords": ["k1"], "description": "d1"},
            {"skill_name": "skill-2", "display_name": "技能2", "category": "planning",
             "trigger_keywords": ["k2"], "description": "d2"},
        ]
        result = sr.bulk_upsert(entries)
        self.assertEqual(result["count"], 2)
        self.assertTrue(sr.get("skill-1")["found"])

    def test_dependencies(self):
        sr = SkillRegistry(self.tmp_db)
        sr.upsert("skill-a", "A", "analysis", [], "desc", ["skill-b"])
        sr.upsert("skill-b", "B", "analysis", [], "desc", ["skill-c"])
        sr.upsert("skill-c", "C", "analysis", [], "desc")
        result = sr.dependencies("skill-a")
        self.assertIn("skill-b", result["dependency_chain"])
        self.assertIn("skill-c", result["dependency_chain"])


# ===== seed_knowledge.py tests =====

class TestSeedKnowledge(InternalDBTestCase):

    def test_seed_all_populates_registry(self):
        sr = SkillRegistry(self.seeded_db)
        result = sr.list_all()
        self.assertEqual(result["count"], len(SKILL_REGISTRY_DATA))
        skill_names = {s["skill_name"] for s in result["skills"]}
        self.assertIn("travel-planner-plugin", skill_names)
        self.assertIn("x-xiake", skill_names)
        self.assertIn("travel-time-pocket", skill_names)

    def test_seed_all_populates_knowledge(self):
        ks = KnowledgeStore(self.seeded_db)
        cats = ks.categories()
        cat_names = {c["name"] for c in cats["categories"]}
        for expected in ("city_info", "intercity_transport", "budget_reference",
                         "accommodation_type", "local_food", "photo_spot",
                         "season_tip", "transit_tip"):
            self.assertIn(expected, cat_names)

    def test_seed_all_idempotent(self):
        seed_all(self.seeded_db)
        seed_all(self.seeded_db)
        sr = SkillRegistry(self.seeded_db)
        self.assertEqual(sr.list_all()["count"], len(SKILL_REGISTRY_DATA))

    def test_seed_city_info_content(self):
        ks = KnowledgeStore(self.seeded_db)
        result = ks.query(category="city_info", key="贵阳")
        self.assertTrue(result["found"])
        self.assertIn("甲秀楼", result["value"]["known_spots"])
        self.assertIn("酸汤鱼", result["value"]["food"])

    def test_seed_intercity_transport_content(self):
        ks = KnowledgeStore(self.seeded_db)
        result = ks.query(category="intercity_transport", key="洛阳→开封")
        self.assertTrue(result["found"])
        self.assertTrue(any(m["type"] == "高铁" for m in result["value"]["modes"]))

    def test_seed_registry_match_travel(self):
        sr = SkillRegistry(self.seeded_db)
        result = sr.match("帮我规划旅游行程")
        self.assertGreaterEqual(result["count"], 1)
        top = result["matched_skills"][0]
        self.assertIn(top["skill_name"],
                      ("travel-planner-plugin", "travel-requirement-analysis"))

    def test_seed_registry_match_photo(self):
        sr = SkillRegistry(self.seeded_db)
        result = sr.match("怎么拍照出片")
        self.assertGreaterEqual(result["count"], 1)
        self.assertTrue(any(s["skill_name"] == "x-xiake"
                            for s in result["matched_skills"]))

    def test_seed_registry_match_accommodation(self):
        sr = SkillRegistry(self.seeded_db)
        result = sr.match("住哪里酒店比价")
        self.assertGreaterEqual(result["count"], 1)
        self.assertTrue(any(s["skill_name"] == "travel-accommodation-advisor"
                            for s in result["matched_skills"]))


# ===== tools.py integration tests =====

class TestToolsIntegration(InternalDBTestCase):

    def test_knowledge_query_action(self):
        tools = TravelTools(internal_db_path=self.seeded_db)
        result = tools.handle(
            {"action": "knowledge_query", "category": "city_info", "key": "贵阳"},
            user_id="test_user",
        )
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["data"]["found"])

    def test_knowledge_query_keyword_action(self):
        tools = TravelTools(internal_db_path=self.seeded_db)
        result = tools.handle(
            {"action": "knowledge_query", "keyword": "高铁"},
            user_id="test_user",
        )
        self.assertEqual(result["status"], "ok")

    def test_knowledge_categories_action(self):
        tools = TravelTools(internal_db_path=self.seeded_db)
        result = tools.handle(
            {"action": "knowledge_categories"},
            user_id="test_user",
        )
        self.assertEqual(result["status"], "ok")
        self.assertGreater(len(result["data"]["categories"]), 0)

    def test_session_put_and_get_action(self):
        tools = TravelTools(internal_db_path=self.tmp_db)
        put_result = tools.handle(
            {"action": "session_put", "trip_id": "trip_test",
             "skill": "travel-requirement-analysis", "stage": "confirmed",
             "key": "requirements", "value": {"city": "贵阳", "days": 3}},
            user_id="test_user",
        )
        self.assertEqual(put_result["status"], "ok")
        get_result = tools.handle(
            {"action": "session_get", "trip_id": "trip_test"},
            user_id="test_user",
        )
        self.assertEqual(get_result["status"], "ok")
        self.assertEqual(get_result["data"]["count"], 1)

    def test_session_get_requirements_action(self):
        tools = TravelTools(internal_db_path=self.tmp_db)
        tools.handle(
            {"action": "session_put", "trip_id": "trip_req",
             "skill": "travel-requirement-analysis", "stage": "confirmed",
             "key": "requirements", "value": {"city": "开封"}},
            user_id="test_user",
        )
        result = tools.handle(
            {"action": "session_get_requirements", "trip_id": "trip_req"},
            user_id="test_user",
        )
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["data"]["found"])
        self.assertEqual(result["data"]["requirements"]["city"], "开封")

    def test_registry_query_action(self):
        tools = TravelTools(internal_db_path=self.seeded_db)
        result = tools.handle(
            {"action": "registry_query", "query": "拍照出片"},
            user_id="test_user",
        )
        self.assertEqual(result["status"], "ok")
        self.assertGreaterEqual(result["data"]["count"], 1)

    def test_registry_list_action(self):
        tools = TravelTools(internal_db_path=self.seeded_db)
        result = tools.handle(
            {"action": "registry_list"},
            user_id="test_user",
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["count"], len(SKILL_REGISTRY_DATA))

    def test_registry_get_action(self):
        tools = TravelTools(internal_db_path=self.seeded_db)
        result = tools.handle(
            {"action": "registry_get", "skill_name": "x-xiake"},
            user_id="test_user",
        )
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["data"]["found"])
        self.assertEqual(result["data"]["display_name"], "拍照出片教练")

    def test_seed_action(self):
        tools = TravelTools(internal_db_path=self.tmp_db)
        result = tools.handle(
            {"action": "seed"},
            user_id="test_user",
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["skill_registry"]["count"],
                         len(SKILL_REGISTRY_DATA))

    def test_knowledge_upsert_invalid_category(self):
        tools = TravelTools(internal_db_path=self.tmp_db)
        result = tools.handle(
            {"action": "knowledge_upsert", "category": "invalid_cat",
             "key": "test", "value": {}},
            user_id="test_user",
        )
        self.assertEqual(result["status"], "invalid")

    def test_session_put_invalid_skill(self):
        tools = TravelTools(internal_db_path=self.tmp_db)
        result = tools.handle(
            {"action": "session_put", "trip_id": "t", "skill": "invalid-skill",
             "stage": "confirmed", "key": "k", "value": "v"},
            user_id="test_user",
        )
        self.assertEqual(result["status"], "invalid")

    def test_preference_actions_still_work(self):
        tools = TravelTools(internal_db_path=self.tmp_db)
        result = tools.handle({"action": "get"}, user_id="test_user")
        self.assertEqual(result["status"], "ok")


if __name__ == "__main__":
    unittest.main()