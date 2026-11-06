"""会话上下文用户归属测试（P1）。

覆盖：
1. 不同用户使用同一 trip_id 时数据互相隔离（写入/读取/需求/行程列表/清空）
2. 旧库无 user_id 时自动迁移，旧数据保留并归属空用户
3. 直接调用 SessionStore 且不传 user_id 时保持旧行为（不过滤）

unittest 风格，CI 可直接运行。
"""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from travel_shared.db import get_connection, init_db
from travel_shared.session import SessionStore
from travel_shared.tools import TravelTools


class SessionOwnershipTest(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp.name) / "internal.sqlite3")
        init_db(self.db)
        self.tools = TravelTools(internal_db_path=self.db)

    def tearDown(self):
        self.temp.cleanup()

    def put(self, trip_id, value, user):
        return self.tools.handle({
            "action": "session_put", "trip_id": trip_id,
            "skill": "travel-requirement-analysis", "stage": "confirmed",
            "key": "requirements", "value": value,
        }, user_id=user)

    def get(self, trip_id, user):
        return self.tools.handle({"action": "session_get", "trip_id": trip_id},
                                 user_id=user)

    # --- 隔离 ---

    def test_same_trip_id_is_isolated_per_user(self):
        self.put("shared", {"city": "贵阳"}, "userA")
        self.put("shared", {"city": "北京"}, "userB")

        a = self.get("shared", "userA")
        b = self.get("shared", "userB")
        self.assertEqual(a["data"]["count"], 1)
        self.assertEqual(b["data"]["count"], 1)
        self.assertEqual(a["data"]["entries"][0]["value"]["city"], "贵阳")
        self.assertEqual(b["data"]["entries"][0]["value"]["city"], "北京")

    def test_requirements_scoped(self):
        self.put("shared", {"city": "贵阳"}, "userA")
        self.put("shared", {"city": "北京"}, "userB")
        a = self.tools.handle({"action": "session_get_requirements",
                               "trip_id": "shared"}, user_id="userA")
        self.assertTrue(a["data"]["found"])
        self.assertEqual(a["data"]["requirements"]["city"], "贵阳")

    def test_list_trips_scoped(self):
        self.put("trip-a", {"v": 1}, "userA")
        self.put("trip-b", {"v": 2}, "userB")
        a = self.tools.handle({"action": "session_list_trips"}, user_id="userA")
        b = self.tools.handle({"action": "session_list_trips"}, user_id="userB")
        self.assertEqual(a["data"]["trips"], ["trip-a"])
        self.assertEqual(b["data"]["trips"], ["trip-b"])

    def test_clear_trip_scoped(self):
        self.put("shared", {"city": "贵阳"}, "userA")
        self.put("shared", {"city": "北京"}, "userB")
        cleared = self.tools.handle({"action": "session_clear_trip",
                                     "trip_id": "shared"}, user_id="userA")
        self.assertEqual(cleared["data"]["deleted"], 1)
        self.assertEqual(self.get("shared", "userA")["data"]["count"], 0)
        self.assertEqual(self.get("shared", "userB")["data"]["count"], 1)

    def test_clear_stage_scoped(self):
        for user, city in (("userA", "贵阳"), ("userB", "北京")):
            self.put("shared", {"city": city}, user)
        cleared = self.tools.handle({
            "action": "session_clear_stage", "trip_id": "shared",
            "skill": "travel-requirement-analysis", "stage": "confirmed",
        }, user_id="userA")
        self.assertEqual(cleared["data"]["deleted"], 1)
        self.assertEqual(self.get("shared", "userB")["data"]["count"], 1)

    # --- 兼容 ---

    def test_store_without_user_id_keeps_legacy_behavior(self):
        store = SessionStore(self.db)
        store.put("legacy-trip", "travel-requirement-analysis", "confirmed",
                  "requirements", {"city": "西安"})
        result = store.get("legacy-trip")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["entries"][0]["value"]["city"], "西安")

    # --- 旧表迁移 ---

    def test_legacy_table_migrates_and_keeps_rows(self):
        path = str(Path(self.temp.name) / "legacy.sqlite3")
        conn = sqlite3.connect(path)
        try:
            conn.executescript("""
                CREATE TABLE session_context (
                    trip_id TEXT NOT NULL, skill TEXT NOT NULL,
                    stage TEXT NOT NULL, key TEXT NOT NULL,
                    value_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY (trip_id, skill, stage, key)
                );
            """)
            conn.execute(
                "INSERT INTO session_context VALUES (?,?,?,?,?,?)",
                ("legacy-trip", "travel-requirement-analysis", "confirmed",
                 "requirements", json.dumps({"city": "贵阳"}), "2026-01-01T00:00:00+00:00"))
            conn.commit()
        finally:
            conn.close()

        migrated = get_connection(path)
        try:
            columns = {row[1] for row in migrated.execute(
                "PRAGMA table_info(session_context)")}
            self.assertIn("user_id", columns)
            rows = migrated.execute(
                "SELECT user_id, trip_id, value_json FROM session_context").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][0], "")
            self.assertEqual(rows[0][1], "legacy-trip")
            self.assertEqual(json.loads(rows[0][2])["city"], "贵阳")
        finally:
            migrated.close()

        # 幂等：再次连接不应重复迁移或报错
        again = get_connection(path)
        try:
            self.assertEqual(again.execute(
                "SELECT COUNT(*) FROM session_context").fetchone()[0], 1)
        finally:
            again.close()

    def test_migrated_legacy_row_visible_only_without_user_scope(self):
        store = SessionStore(self.db)
        store.put("legacy-trip", "travel-requirement-analysis", "confirmed",
                  "requirements", {"city": "西安"})
        # 空用户写入后，按具体用户查询不应看到
        result = store.get("legacy-trip", user_id="userX")
        self.assertEqual(result["count"], 0)


if __name__ == "__main__":
    unittest.main()