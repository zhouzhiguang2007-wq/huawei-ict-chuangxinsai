"""数据库未初始化保护（P0-3）测试。

覆盖：
1. 内部库文件不存在（等价“未建表”）
2. 库文件存在但 guided_questions 表缺失
3. 表已建但为空（未运行 seed_knowledge）
4. 已 seed 后 prepare 正常返回
5. 问卷 / 知识库空结果时的排障 hint

unittest 风格，CI 的 unittest discover 可直接运行。
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from travel_shared.db import init_db
from travel_shared.seed_knowledge import seed_all
from travel_shared.tools import TravelTools


def context(skill="travel-requirement-analysis"):
    return {
        "schema_version": "1.0",
        "trip_id": "seed-guard-trip",
        "skill": skill,
        "requirements": {
            "destination": {"city": "贵阳"},
            "dates": {"start_date": "2027-02-01", "days": 2},
            "travelers": {"total": 2, "adults": 2},
            "budget": {"amount": 3000, "currency": "CNY",
                       "scope": "total_trip", "hard_limit": True},
            "preferences": {},
        },
        "payload": {},
    }


class SeedGuardTest(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.pref_db = base / "preferences.sqlite3"
        self.internal_db = base / "internal.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def tools(self, internal_db=None):
        return TravelTools(self.pref_db,
                           internal_db_path=str(internal_db or self.internal_db))

    def prepare(self, tools):
        return tools.handle({"action": "prepare", "context": context()},
                            user_id="tester")

    # --- prepare 就绪检查 ---

    def test_prepare_blocks_when_db_file_missing(self):
        result = self.prepare(self.tools())
        self.assertEqual(result["status"], "unavailable")
        self.assertIs(result["data"]["ok"], False)
        self.assertEqual(result["data"]["reason"], "db_not_seeded")
        self.assertIn("seed_knowledge", result["data"]["fix"])
        self.assertTrue(result["errors"])

    def test_prepare_blocks_when_table_missing(self):
        conn = sqlite3.connect(str(self.internal_db))
        try:
            conn.execute("CREATE TABLE unrelated (id INTEGER)")
            conn.commit()
        finally:
            conn.close()
        result = self.prepare(self.tools())
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["data"]["reason"], "db_not_seeded")

    def test_prepare_blocks_when_table_empty(self):
        init_db(str(self.internal_db))
        result = self.prepare(self.tools())
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["data"]["reason"], "db_not_seeded")

    def test_prepare_ok_after_seed(self):
        init_db(str(self.internal_db))
        seed_all(str(self.internal_db))
        result = self.prepare(self.tools())
        self.assertEqual(result["status"], "ok")
        self.assertIn("context", result["data"])
        self.assertNotEqual(result["data"].get("reason"), "db_not_seeded")

    # --- 问卷 hint ---

    def test_questionnaire_hint_when_empty(self):
        init_db(str(self.internal_db))
        tools = self.tools()
        result = tools.handle({"action": "questionnaire_get_step", "step": 1},
                              user_id="tester")
        self.assertEqual(result["status"], "ok")
        self.assertIs(result["data"]["found"], False)
        self.assertIn("hint", result["data"])
        self.assertIn("seed_knowledge", result["data"]["hint"])

    def test_questionnaire_list_hint_when_empty(self):
        init_db(str(self.internal_db))
        tools = self.tools()
        result = tools.handle({"action": "questionnaire_list"}, user_id="tester")
        self.assertEqual(result["data"]["count"], 0)
        self.assertIn("hint", result["data"])

    def test_questionnaire_no_hint_after_seed(self):
        init_db(str(self.internal_db))
        seed_all(str(self.internal_db))
        tools = self.tools()
        result = tools.handle({"action": "questionnaire_get_step", "step": 1},
                              user_id="tester")
        self.assertEqual(result["status"], "ok")
        self.assertIs(result["data"]["found"], True)
        self.assertNotIn("hint", result["data"])

    def test_questionnaire_missing_step_no_false_alarm(self):
        init_db(str(self.internal_db))
        seed_all(str(self.internal_db))
        tools = self.tools()
        result = tools.handle({"action": "questionnaire_get_step", "step": 999},
                              user_id="tester")
        self.assertIs(result["data"]["found"], False)
        # 库已有数据，只是该步不存在，不应提示“未初始化”
        self.assertNotIn("hint", result["data"])

    # --- 知识库 hint ---

    def test_knowledge_hint_when_empty(self):
        init_db(str(self.internal_db))
        tools = self.tools()
        result = tools.handle({"action": "knowledge_query", "category": "city_info",
                               "key": "贵阳"}, user_id="tester")
        self.assertIs(result["data"]["found"], False)
        self.assertIn("hint", result["data"])
        self.assertIn("seed_knowledge", result["data"]["hint"])

    def test_knowledge_no_hint_when_data_exists(self):
        init_db(str(self.internal_db))
        seed_all(str(self.internal_db))
        tools = self.tools()
        result = tools.handle({"action": "knowledge_query", "category": "city_info",
                               "key": "不存在的城市"}, user_id="tester")
        self.assertIs(result["data"]["found"], False)
        self.assertNotIn("hint", result["data"])

    def test_knowledge_hint_absent_when_table_populated_manually(self):
        init_db(str(self.internal_db))
        tools = self.tools()
        tools.handle({"action": "knowledge_upsert", "category": "city_info",
                      "key": "测试城", "value": {"spots": ["A"]}}, user_id="tester")
        result = tools.handle({"action": "knowledge_query", "category": "city_info",
                               "key": "另一个城"}, user_id="tester")
        self.assertIs(result["data"]["found"], False)
        self.assertNotIn("hint", result["data"])


if __name__ == "__main__":
    unittest.main()