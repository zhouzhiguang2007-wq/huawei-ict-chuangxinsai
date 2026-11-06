"""偏好迁移脚本测试（P1）。

覆盖：源库缺失/空表、正常插入、冲突保留较新、冲突更新、dry-run、备份。
unittest 风格，CI 可直接运行。
"""

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import migrate_preferences  # noqa: E402

_CREATE = """
CREATE TABLE IF NOT EXISTS preferences (
    user_id TEXT NOT NULL, field TEXT NOT NULL, value_json TEXT NOT NULL,
    source TEXT NOT NULL, updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, field)
);
"""


def make_prefs(path, rows):
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(_CREATE)
        conn.executemany(
            "INSERT INTO preferences (user_id, field, value_json, source, updated_at) "
            "VALUES (?,?,?,?,?)", rows)
        conn.commit()
    finally:
        conn.close()


def read_prefs(path):
    conn = sqlite3.connect(str(path))
    try:
        return conn.execute(
            "SELECT user_id, field, value_json, source, updated_at "
            "FROM preferences ORDER BY user_id, field").fetchall()
    finally:
        conn.close()


class MigratePreferencesTest(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.source = base / "old_preferences.sqlite3"
        self.target = base / "internal.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def test_missing_source_is_skipped(self):
        report = migrate_preferences.migrate(self.source, self.target)
        self.assertEqual(report["status"], "skipped_no_source")
        self.assertFalse(self.target.exists())

    def test_empty_source_is_skipped(self):
        make_prefs(self.source, [])
        report = migrate_preferences.migrate(self.source, self.target)
        self.assertEqual(report["status"], "skipped_empty_source")
        self.assertEqual(report["source_rows"], 0)

    def test_inserts_rows(self):
        make_prefs(self.source, [
            ("alice", "pace", json.dumps("relaxed"), "用户确认", "2026-01-01T00:00:00+00:00"),
            ("alice", "interests", json.dumps(["自然"]), "用户确认", "2026-01-02T00:00:00+00:00"),
        ])
        report = migrate_preferences.migrate(self.source, self.target)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["inserted"], 2)
        self.assertEqual(report["updated"], 0)

        rows = read_prefs(self.target)
        self.assertEqual(len(rows), 2)
        by_field = {row[1]: json.loads(row[2]) for row in rows}
        self.assertEqual(by_field["pace"], "relaxed")
        self.assertEqual(by_field["interests"], ["自然"])

    def test_conflict_keeps_newer_target(self):
        make_prefs(self.target, [
            ("alice", "pace", json.dumps("intensive"), "较新", "2026-02-01T00:00:00+00:00"),
        ])
        make_prefs(self.source, [
            ("alice", "pace", json.dumps("relaxed"), "较旧", "2026-01-01T00:00:00+00:00"),
        ])
        report = migrate_preferences.migrate(self.source, self.target)
        self.assertEqual(report["skipped"], 1)
        self.assertEqual(report["updated"], 0)
        rows = read_prefs(self.target)
        self.assertEqual(json.loads(rows[0][2]), "intensive")

    def test_conflict_updates_when_source_newer(self):
        make_prefs(self.target, [
            ("alice", "pace", json.dumps("intensive"), "较旧", "2026-01-01T00:00:00+00:00"),
        ])
        make_prefs(self.source, [
            ("alice", "pace", json.dumps("relaxed"), "较新", "2026-02-01T00:00:00+00:00"),
        ])
        report = migrate_preferences.migrate(self.source, self.target)
        self.assertEqual(report["updated"], 1)
        rows = read_prefs(self.target)
        self.assertEqual(json.loads(rows[0][2]), "relaxed")

    def test_dry_run_writes_nothing(self):
        make_prefs(self.source, [
            ("bob", "pace", json.dumps("balanced"), "用户确认", "2026-01-01T00:00:00+00:00"),
        ])
        report = migrate_preferences.migrate(self.source, self.target, dry_run=True)
        self.assertEqual(report["status"], "dry_run")
        self.assertEqual(report["source_rows"], 1)
        self.assertFalse(self.target.exists())

    def test_backup_created_when_target_exists(self):
        make_prefs(self.target, [
            ("carol", "pace", json.dumps("relaxed"), "已有", "2026-01-01T00:00:00+00:00"),
        ])
        make_prefs(self.source, [
            ("dave", "pace", json.dumps("balanced"), "用户确认", "2026-01-01T00:00:00+00:00"),
        ])
        report = migrate_preferences.migrate(self.source, self.target)
        self.assertIsNotNone(report["backup"])
        self.assertTrue(Path(report["backup"]).exists())
        self.assertEqual(len(read_prefs(self.target)), 2)

    def test_backup_can_be_disabled(self):
        make_prefs(self.target, [("carol", "pace", json.dumps("relaxed"), "x", "2026-01-01T00:00:00+00:00")])
        make_prefs(self.source, [("dave", "pace", json.dumps("balanced"), "y", "2026-01-01T00:00:00+00:00")])
        report = migrate_preferences.migrate(self.source, self.target, backup=False)
        self.assertIsNone(report["backup"])

    def test_same_timestamp_keeps_both_backups(self):
        make_prefs(self.target, [("carol", "pace", json.dumps("relaxed"), "已有", "2026-01-01T00:00:00+00:00")])
        make_prefs(self.source, [("dave", "pace", json.dumps("balanced"), "用户确认", "2026-01-01T00:00:00+00:00")])

        class FixedClock:
            @staticmethod
            def now():
                return datetime(2026, 1, 2, 3, 4, 5, 123000)

        with patch.object(migrate_preferences, "datetime", FixedClock):
            first = migrate_preferences.migrate(self.source, self.target)
            second = migrate_preferences.migrate(self.source, self.target)

        first_backup = Path(first["backup"])
        second_backup = Path(second["backup"])
        self.assertNotEqual(first_backup, second_backup)
        self.assertTrue(first_backup.exists())
        self.assertTrue(second_backup.exists())
        self.assertEqual(len(read_prefs(first_backup)), 1)
        self.assertEqual(len(read_prefs(second_backup)), 2)

    def test_cli_returns_zero(self):
        make_prefs(self.source, [
            ("erin", "pace", json.dumps("relaxed"), "用户确认", "2026-01-01T00:00:00+00:00"),
        ])
        code = migrate_preferences.main([
            "--from", str(self.source), "--to", str(self.target), "--no-backup"])
        self.assertEqual(code, 0)
        self.assertEqual(len(read_prefs(self.target)), 1)


if __name__ == "__main__":
    unittest.main()
