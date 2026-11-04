"""Tests for the internal private database modules (A/B/C).

Tests cover:
  - db.py: schema initialization
  - knowledge.py (Module A): query, upsert, bulk_upsert, categories, delete
  - session.py (Module B): put, get, get_requirements, list_trips, clear
  - registry.py (Module C): get, list_all, match, upsert, dependencies
  - seed_knowledge.py: seed_all populates all tables
  - tools.py: new actions wired correctly
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import sqlite3
import pytest

from travel_shared.db import get_connection, init_db
from travel_shared.knowledge import KnowledgeStore
from travel_shared.session import SessionStore
from travel_shared.registry import SkillRegistry
from travel_shared.seed_knowledge import seed_all, SKILL_REGISTRY_DATA, TRAVEL_KNOWLEDGE_DATA
from travel_shared.tools import TravelTools


@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / "test_internal.sqlite3"
    init_db(str(db_path))
    return str(db_path)


@pytest.fixture
def seeded_db(tmp_path):
    db_path = tmp_path / "test_seeded.sqlite3"
    init_db(str(db_path))
    seed_all(str(db_path))
    return str(db_path)


# ===== db.py tests =====

class TestDB:

    def test_init_creates_tables(self, tmp_db):
        conn = get_connection(tmp_db)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        assert "travel_knowledge" in tables
        assert "session_context" in tables
        assert "skill_registry" in tables

    def test_init_creates_indexes(self, tmp_db):
        conn = get_connection(tmp_db)
        indexes = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()}
        conn.close()
        assert "idx_knowledge_category" in indexes
        assert "idx_session_owner_trip" in indexes
        assert "idx_session_owner_skill" in indexes

    def test_idempotent_init(self, tmp_db):
        init_db(tmp_db)
        init_db(tmp_db)
        conn = get_connection(tmp_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM travel_knowledge"
        ).fetchone()[0]
        conn.close()
        assert count == 0

    def test_seed_command_and_tool_share_configured_internal_db(self, tmp_path):
        internal_db = tmp_path / "configured-internal.sqlite3"
        request_file = tmp_path / "query.json"
        request_file.write_text(
            json.dumps({"action": "knowledge_query", "category": "city_info",
                        "key": "开封"}, ensure_ascii=False), encoding="utf-8"
        )
        env = dict(os.environ, TRAVEL_INTERNAL_DB=str(internal_db))
        root = Path(__file__).resolve().parents[1]
        seeded = subprocess.run(
            [sys.executable, "-B", "-m", "travel_shared.seed_knowledge"],
            cwd=root, env=env, capture_output=True, text=True, encoding="utf-8"
        )
        assert seeded.returncode == 0, seeded.stderr
        queried = subprocess.run(
            [sys.executable, "-B", "-m", "travel_shared",
             "--db", str(tmp_path / "preferences.sqlite3"),
             "--user-id", "demo", str(request_file)],
            cwd=root, env=env, capture_output=True, text=True, encoding="utf-8"
        )
        assert queried.returncode == 0, queried.stderr
        assert json.loads(queried.stdout)["data"]["found"] is True
        assert internal_db.is_file()


# ===== Module A: KnowledgeStore tests =====

class TestKnowledgeStore:

    def test_upsert_and_query_exact(self, tmp_db):
        ks = KnowledgeStore(tmp_db)
        ks.upsert("city_info", "测试城市",
                  {"province": "测试省", "known_spots": ["景点A"]})
        result = ks.query(category="city_info", key="测试城市")
        assert result["found"] is True
        assert result["value"]["province"] == "测试省"
        assert result["value"]["known_spots"] == ["景点A"]

    def test_query_not_found(self, tmp_db):
        ks = KnowledgeStore(tmp_db)
        result = ks.query(category="city_info", key="不存在")
        assert result["found"] is False

    def test_query_by_category(self, tmp_db):
        ks = KnowledgeStore(tmp_db)
        ks.upsert("city_info", "城市A", {"spots": ["a"]})
        ks.upsert("city_info", "城市B", {"spots": ["b"]})
        ks.upsert("budget_reference", "经济型", {"range": "100-300"})
        result = ks.query(category="city_info")
        assert result["found"] is True
        assert len(result["results"]) == 2

    def test_query_by_keyword(self, tmp_db):
        ks = KnowledgeStore(tmp_db)
        ks.upsert("city_info", "贵阳", {"known_spots": ["甲秀楼"]})
        ks.upsert("local_food", "贵州", {"signature_dishes": ["酸汤鱼"]})
        result = ks.query(keyword="贵阳")
        assert result["found"] is True
        assert len(result["results"]) >= 1

    def test_bulk_upsert(self, tmp_db):
        ks = KnowledgeStore(tmp_db)
        entries = [
            {"category": "city_info", "key": "城市C", "value": {"spots": ["c"]}},
            {"category": "city_info", "key": "城市D", "value": {"spots": ["d"]}},
        ]
        result = ks.bulk_upsert(entries)
        assert result["count"] == 2
        assert ks.query(category="city_info", key="城市C")["found"] is True
        assert ks.query(category="city_info", key="城市D")["found"] is True

    def test_upsert_overwrites(self, tmp_db):
        ks = KnowledgeStore(tmp_db)
        ks.upsert("city_info", "城市E", {"v": 1})
        ks.upsert("city_info", "城市E", {"v": 2})
        result = ks.query(category="city_info", key="城市E")
        assert result["value"]["v"] == 2

    def test_categories(self, tmp_db):
        ks = KnowledgeStore(tmp_db)
        ks.upsert("city_info", "A", {})
        ks.upsert("budget_reference", "B", {})
        cats = ks.categories()
        names = [c["name"] for c in cats["categories"]]
        assert "city_info" in names
        assert "budget_reference" in names

    def test_delete(self, tmp_db):
        ks = KnowledgeStore(tmp_db)
        ks.upsert("city_info", "ToDelete", {"v": 1})
        result = ks.delete("city_info", "ToDelete")
        assert result["deleted"] == 1
        assert ks.query(category="city_info", key="ToDelete")["found"] is False


# ===== Module B: SessionStore tests =====

class TestSessionStore:

    def test_put_and_get(self, tmp_db):
        ss = SessionStore(tmp_db)
        ss.put("trip_001", "travel-requirement-analysis", "confirmed",
               "requirements", {"city": "贵阳", "days": 3})
        result = ss.get("trip_001")
        assert result["count"] == 1
        entry = result["entries"][0]
        assert entry["skill"] == "travel-requirement-analysis"
        assert entry["stage"] == "confirmed"
        assert entry["key"] == "requirements"
        assert entry["value"]["city"] == "贵阳"

    def test_put_overwrites(self, tmp_db):
        ss = SessionStore(tmp_db)
        ss.put("trip_001", "travel-requirement-analysis", "confirmed",
               "requirements", {"city": "贵阳"})
        ss.put("trip_001", "travel-requirement-analysis", "confirmed",
               "requirements", {"city": "开封"})
        result = ss.get("trip_001")
        assert result["count"] == 1
        assert result["entries"][0]["value"]["city"] == "开封"

    def test_get_filtered_by_skill(self, tmp_db):
        ss = SessionStore(tmp_db)
        ss.put("trip_001", "travel-requirement-analysis", "confirmed",
               "requirements", {"city": "贵阳"})
        ss.put("trip_001", "multi-platform-travel-planner", "candidate",
               "spots", ["甲秀楼", "黔灵山"])
        result = ss.get("trip_001", skill="travel-requirement-analysis")
        assert result["count"] == 1
        assert result["entries"][0]["key"] == "requirements"

    def test_get_filtered_by_stage(self, tmp_db):
        ss = SessionStore(tmp_db)
        ss.put("trip_001", "multi-platform-travel-planner", "candidate",
               "spots", ["甲秀楼"])
        ss.put("trip_001", "multi-platform-travel-planner", "verified",
               "weather", {"sunny": True})
        result = ss.get("trip_001", skill="multi-platform-travel-planner",
                        stage="candidate")
        assert result["count"] == 1
        assert result["entries"][0]["key"] == "spots"

    def test_get_requirements(self, tmp_db):
        ss = SessionStore(tmp_db)
        ss.put("trip_001", "travel-requirement-analysis", "confirmed",
               "requirements", {"city": "贵阳", "days": 3, "budget": 3000})
        result = ss.get_requirements("trip_001")
        assert result["found"] is True
        assert result["requirements"]["city"] == "贵阳"
        assert result["requirements"]["days"] == 3

    def test_get_requirements_not_found(self, tmp_db):
        ss = SessionStore(tmp_db)
        result = ss.get_requirements("trip_999")
        assert result["found"] is False

    def test_list_trips(self, tmp_db):
        ss = SessionStore(tmp_db)
        ss.put("trip_A", "travel-requirement-analysis", "confirmed", "k", "v")
        ss.put("trip_B", "travel-requirement-analysis", "confirmed", "k", "v")
        result = ss.list_trips()
        assert "trip_A" in result["trips"]
        assert "trip_B" in result["trips"]

    def test_clear_trip(self, tmp_db):
        ss = SessionStore(tmp_db)
        ss.put("trip_001", "travel-requirement-analysis", "confirmed", "k", "v")
        ss.put("trip_001", "multi-platform-travel-planner", "candidate", "k2", "v2")
        result = ss.clear_trip("trip_001")
        assert result["deleted"] == 2
        assert ss.get("trip_001")["count"] == 0

    def test_clear_stage(self, tmp_db):
        ss = SessionStore(tmp_db)
        ss.put("trip_001", "travel-requirement-analysis", "confirmed", "k", "v")
        ss.put("trip_001", "travel-requirement-analysis", "candidate", "k2", "v2")
        result = ss.clear_stage("trip_001", "travel-requirement-analysis", "confirmed")
        assert result["deleted"] == 1
        assert ss.get("trip_001")["count"] == 1

    def test_same_trip_id_is_isolated_for_get_list_and_delete(self, tmp_db):
        ss = SessionStore(tmp_db)
        for user, city in (("alice", "贵阳"), ("bob", "开封")):
            ss.put("same-trip", "travel-requirement-analysis", "confirmed",
                   "requirements", {"city": city}, user_id=user)
        ss.put("alice-only", "travel-requirement-analysis", "confirmed",
               "requirements", {"city": "洛阳"}, user_id="alice")
        assert ss.get_requirements("same-trip", user_id="alice")["requirements"]["city"] == "贵阳"
        assert ss.get_requirements("same-trip", user_id="bob")["requirements"]["city"] == "开封"
        assert ss.list_trips(user_id="alice")["trips"] == ["alice-only", "same-trip"]
        assert ss.list_trips(user_id="bob")["trips"] == ["same-trip"]
        assert ss.clear_stage("same-trip", "travel-requirement-analysis",
                              "confirmed", user_id="bob")["deleted"] == 1
        assert ss.get("same-trip", user_id="alice")["count"] == 1
        assert ss.clear_trip("alice-only", user_id="bob")["deleted"] == 0
        assert ss.get("alice-only", user_id="alice")["count"] == 1

    def test_legacy_sessions_are_preserved_but_not_claimed(self, tmp_path):
        legacy_db = tmp_path / "legacy.sqlite3"
        conn = sqlite3.connect(str(legacy_db))
        conn.execute(
            "CREATE TABLE session_context (trip_id TEXT NOT NULL, "
            "skill TEXT NOT NULL, stage TEXT NOT NULL, key TEXT NOT NULL, "
            "value_json TEXT NOT NULL, created_at TEXT NOT NULL, "
            "PRIMARY KEY (trip_id, skill, stage, key))"
        )
        conn.execute(
            "INSERT INTO session_context VALUES (?,?,?,?,?,?)",
            ("old-trip", "travel-requirement-analysis", "confirmed",
             "requirements", '{"city":"private"}', "2026-11-03T00:00:00+00:00"),
        )
        conn.commit()
        conn.close()

        init_db(str(legacy_db))
        ss = SessionStore(str(legacy_db))
        for user in ("alice", "bob", ""):
            assert ss.get("old-trip", user_id=user)["count"] == 0
            assert ss.list_trips(user_id=user)["trips"] == []
        with pytest.raises(ValueError):
            ss.get("old-trip", user_id="\x00legacy-unassigned")
        conn = get_connection(str(legacy_db))
        try:
            assert conn.execute(
                "SELECT COUNT(*) FROM session_context_legacy"
            ).fetchone()[0] == 1
            assert conn.execute(
                "SELECT COUNT(*) FROM session_context WHERE trip_id='old-trip'"
            ).fetchone()[0] == 1
        finally:
            conn.close()
        ss.put("old-trip", "travel-requirement-analysis", "confirmed",
               "requirements", {"city": "new"}, user_id="alice")
        assert ss.get("old-trip", user_id="alice")["entries"][0]["value"]["city"] == "new"


# ===== Module C: SkillRegistry tests =====

class TestSkillRegistry:

    def test_upsert_and_get(self, tmp_db):
        sr = SkillRegistry(tmp_db)
        sr.upsert("test-skill", "测试技能", "analysis",
                  ["测试", "技能"], "这是一个测试技能",
                  ["dep1"], "输出测试结果")
        result = sr.get("test-skill")
        assert result["found"] is True
        assert result["display_name"] == "测试技能"
        assert result["trigger_keywords"] == ["测试", "技能"]
        assert result["dependencies"] == ["dep1"]

    def test_get_not_found(self, tmp_db):
        sr = SkillRegistry(tmp_db)
        result = sr.get("nonexistent")
        assert result["found"] is False

    def test_list_all(self, tmp_db):
        sr = SkillRegistry(tmp_db)
        sr.upsert("skill-a", "技能A", "analysis", ["a"], "desc a")
        sr.upsert("skill-b", "技能B", "planning", ["b"], "desc b")
        result = sr.list_all()
        assert result["count"] == 2

    def test_match_by_keyword(self, tmp_db):
        sr = SkillRegistry(tmp_db)
        sr.upsert("photo-skill", "拍照技能", "photo",
                  ["拍照", "出片", "机位"], "拍照指导")
        sr.upsert("food-skill", "美食技能", "planning",
                  ["美食", "吃"], "美食推荐")
        result = sr.match("我想拍照出片")
        assert result["count"] >= 1
        assert result["matched_skills"][0]["skill_name"] == "photo-skill"

    def test_match_no_results(self, tmp_db):
        sr = SkillRegistry(tmp_db)
        sr.upsert("skill-a", "技能A", "analysis", ["a"], "desc a")
        result = sr.match("完全不匹配的查询")
        assert result["count"] == 0

    def test_bulk_upsert(self, tmp_db):
        sr = SkillRegistry(tmp_db)
        entries = [
            {"skill_name": "skill-1", "display_name": "技能1", "category": "analysis",
             "trigger_keywords": ["k1"], "description": "d1"},
            {"skill_name": "skill-2", "display_name": "技能2", "category": "planning",
             "trigger_keywords": ["k2"], "description": "d2"},
        ]
        result = sr.bulk_upsert(entries)
        assert result["count"] == 2
        assert sr.get("skill-1")["found"] is True

    def test_dependencies(self, tmp_db):
        sr = SkillRegistry(tmp_db)
        sr.upsert("skill-a", "A", "analysis", [], "desc", ["skill-b"])
        sr.upsert("skill-b", "B", "analysis", [], "desc", ["skill-c"])
        sr.upsert("skill-c", "C", "analysis", [], "desc")
        result = sr.dependencies("skill-a")
        assert "skill-b" in result["dependency_chain"]
        assert "skill-c" in result["dependency_chain"]


# ===== seed_knowledge.py tests =====

class TestSeedKnowledge:

    def test_seed_all_populates_registry(self, seeded_db):
        sr = SkillRegistry(seeded_db)
        result = sr.list_all()
        assert result["count"] == len(SKILL_REGISTRY_DATA)
        skill_names = {s["skill_name"] for s in result["skills"]}
        assert "travel-planner-plugin" in skill_names
        assert "x-xiake" in skill_names
        assert "travel-time-pocket" in skill_names

    def test_seed_all_populates_knowledge(self, seeded_db):
        ks = KnowledgeStore(seeded_db)
        cats = ks.categories()
        cat_names = {c["name"] for c in cats["categories"]}
        assert "city_info" in cat_names
        assert "intercity_transport" in cat_names
        assert "budget_reference" in cat_names
        assert "accommodation_type" in cat_names
        assert "local_food" in cat_names
        assert "photo_spot" in cat_names
        assert "season_tip" in cat_names
        assert "transit_tip" in cat_names

    def test_seed_all_idempotent(self, tmp_path):
        db_path = str(tmp_path / "test_idempotent.sqlite3")
        init_db(db_path)
        seed_all(db_path)
        seed_all(db_path)
        sr = SkillRegistry(db_path)
        assert sr.list_all()["count"] == len(SKILL_REGISTRY_DATA)

    def test_seed_city_info_content(self, seeded_db):
        ks = KnowledgeStore(seeded_db)
        result = ks.query(category="city_info", key="贵阳")
        assert result["found"] is True
        assert "甲秀楼" in result["value"]["known_spots"]
        assert "酸汤鱼" in result["value"]["food"]

    def test_seed_intercity_transport_content(self, seeded_db):
        ks = KnowledgeStore(seeded_db)
        result = ks.query(category="intercity_transport", key="洛阳→开封")
        assert result["found"] is True
        assert any(m["type"] == "高铁" for m in result["value"]["modes"])

    def test_seed_registry_match_travel(self, seeded_db):
        sr = SkillRegistry(seeded_db)
        result = sr.match("帮我规划旅游行程")
        assert result["count"] >= 1
        top = result["matched_skills"][0]
        assert top["skill_name"] in ("travel-planner-plugin",
                                      "travel-requirement-analysis")

    def test_seed_registry_match_photo(self, seeded_db):
        sr = SkillRegistry(seeded_db)
        result = sr.match("怎么拍照出片")
        assert result["count"] >= 1
        assert any(s["skill_name"] == "x-xiake" for s in result["matched_skills"])

    def test_seed_registry_match_accommodation(self, seeded_db):
        sr = SkillRegistry(seeded_db)
        result = sr.match("住哪里酒店比价")
        assert result["count"] >= 1
        assert any(s["skill_name"] == "travel-accommodation-advisor"
                    for s in result["matched_skills"])


# ===== tools.py integration tests =====

class TestToolsIntegration:

    def test_knowledge_query_action(self, seeded_db):
        tools = TravelTools(internal_db_path=seeded_db)
        result = tools.handle(
            {"action": "knowledge_query", "category": "city_info", "key": "贵阳"},
            user_id="test_user",
        )
        assert result["status"] == "ok"
        assert result["data"]["found"] is True

    def test_knowledge_query_keyword_action(self, seeded_db):
        tools = TravelTools(internal_db_path=seeded_db)
        result = tools.handle(
            {"action": "knowledge_query", "keyword": "高铁"},
            user_id="test_user",
        )
        assert result["status"] == "ok"

    def test_knowledge_categories_action(self, seeded_db):
        tools = TravelTools(internal_db_path=seeded_db)
        result = tools.handle(
            {"action": "knowledge_categories"},
            user_id="test_user",
        )
        assert result["status"] == "ok"
        assert len(result["data"]["categories"]) > 0

    def test_session_put_and_get_action(self, tmp_db):
        tools = TravelTools(internal_db_path=tmp_db)
        put_result = tools.handle(
            {"action": "session_put", "trip_id": "trip_test",
             "skill": "travel-requirement-analysis", "stage": "confirmed",
             "key": "requirements", "value": {"city": "贵阳", "days": 3}},
            user_id="test_user",
        )
        assert put_result["status"] == "ok"
        get_result = tools.handle(
            {"action": "session_get", "trip_id": "trip_test"},
            user_id="test_user",
        )
        assert get_result["status"] == "ok"
        assert get_result["data"]["count"] == 1

    def test_session_get_requirements_action(self, tmp_db):
        tools = TravelTools(internal_db_path=tmp_db)
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
        assert result["status"] == "ok"
        assert result["data"]["found"] is True
        assert result["data"]["requirements"]["city"] == "开封"

    def test_registry_query_action(self, seeded_db):
        tools = TravelTools(internal_db_path=seeded_db)
        result = tools.handle(
            {"action": "registry_query", "query": "拍照出片"},
            user_id="test_user",
        )
        assert result["status"] == "ok"
        assert result["data"]["count"] >= 1

    def test_registry_list_action(self, seeded_db):
        tools = TravelTools(internal_db_path=seeded_db)
        result = tools.handle(
            {"action": "registry_list"},
            user_id="test_user",
        )
        assert result["status"] == "ok"
        assert result["data"]["count"] == len(SKILL_REGISTRY_DATA)

    def test_registry_get_action(self, seeded_db):
        tools = TravelTools(internal_db_path=seeded_db)
        result = tools.handle(
            {"action": "registry_get", "skill_name": "x-xiake"},
            user_id="test_user",
        )
        assert result["status"] == "ok"
        assert result["data"]["found"] is True
        assert result["data"]["display_name"] == "拍照出片教练"

    def test_seed_action(self, tmp_db):
        tools = TravelTools(internal_db_path=tmp_db)
        result = tools.handle(
            {"action": "seed"},
            user_id="test_user",
        )
        assert result["status"] == "ok"
        assert result["data"]["skill_registry"]["count"] == len(SKILL_REGISTRY_DATA)

    def test_knowledge_upsert_invalid_category(self, tmp_db):
        tools = TravelTools(internal_db_path=tmp_db)
        result = tools.handle(
            {"action": "knowledge_upsert", "category": "invalid_cat",
             "key": "test", "value": {}},
            user_id="test_user",
        )
        assert result["status"] == "invalid"

    def test_session_put_invalid_skill(self, tmp_db):
        tools = TravelTools(internal_db_path=tmp_db)
        result = tools.handle(
            {"action": "session_put", "trip_id": "t", "skill": "invalid-skill",
             "stage": "confirmed", "key": "k", "value": "v"},
            user_id="test_user",
        )
        assert result["status"] == "invalid"

    def test_preference_actions_still_work(self, tmp_db):
        tools = TravelTools(internal_db_path=tmp_db)
        result = tools.handle(
            {"action": "get"},
            user_id="test_user",
        )
        assert result["status"] == "ok"
