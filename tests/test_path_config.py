"""数据库路径配置一致性测试（P1）。

验证三处使用同一个解析函数，避免「初始化写默认位置、启动读自定义位置」：

1. `travel_shared.db.default_internal_db_path()` 读取 `TRAVEL_INTERNAL_DB`
2. `travel_shared.tools.DEFAULT_INTERNAL_DB` 与 resolver 一致
3. `python -m travel_shared.seed_knowledge` 写入 `TRAVEL_INTERNAL_DB` 指定路径，
   不再写入默认 `~/.travel-planner/internal.sqlite3`

全部通过子进程隔离 HOME，避免污染本机数据库。unittest 风格，CI 可直接运行。
"""

import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PathConfigTest(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.home = base / "home"
        self.custom = base / "custom"
        self.home.mkdir()
        self.custom.mkdir()
        self.env = dict(os.environ)
        self.env["HOME"] = str(self.home)
        self.env["USERPROFILE"] = str(self.home)
        self.env["TRAVEL_INTERNAL_DB"] = str(self.custom / "internal.sqlite3")
        self.env.pop("TRAVEL_PREFERENCES_DB", None)

    def tearDown(self):
        self.temp.cleanup()

    def run_python(self, code):
        return subprocess.run([sys.executable, "-c", code], cwd=str(ROOT),
                              env=self.env, capture_output=True, text=True,
                              encoding="utf-8")

    def test_resolver_reads_env(self):
        result = self.run_python(
            "from travel_shared.db import default_internal_db_path as p; print(p())")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout.strip()),
                         Path(self.env["TRAVEL_INTERNAL_DB"]))

    def test_resolver_falls_back_to_home(self):
        env = dict(self.env)
        env.pop("TRAVEL_INTERNAL_DB", None)
        result = subprocess.run(
            [sys.executable, "-c",
             "from travel_shared.db import default_internal_db_path as p; print(p())"],
            cwd=str(ROOT), env=env, capture_output=True, text=True,
            encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = self.home / ".travel-planner" / "internal.sqlite3"
        self.assertEqual(Path(result.stdout.strip()), expected)

    def test_tools_defaults_match_resolver(self):
        result = self.run_python(
            "from travel_shared.tools import DEFAULT_INTERNAL_DB, DEFAULT_DB;"
            "print(DEFAULT_INTERNAL_DB); print(DEFAULT_DB)")
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
        expected = Path(self.env["TRAVEL_INTERNAL_DB"])
        self.assertEqual(Path(lines[0]), expected)
        self.assertEqual(Path(lines[1]), expected)

    def test_tools_preference_env_overrides(self):
        env = dict(self.env)
        env["TRAVEL_PREFERENCES_DB"] = str(self.custom / "prefs.sqlite3")
        result = subprocess.run(
            [sys.executable, "-c",
             "from travel_shared.tools import DEFAULT_INTERNAL_DB, DEFAULT_DB;"
             "print(DEFAULT_INTERNAL_DB); print(DEFAULT_DB)"],
            cwd=str(ROOT), env=env, capture_output=True, text=True,
            encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
        self.assertEqual(Path(lines[0]), Path(env["TRAVEL_INTERNAL_DB"]))
        self.assertEqual(Path(lines[1]), Path(env["TRAVEL_PREFERENCES_DB"]))

    def test_seed_cli_writes_custom_path_not_default(self):
        result = subprocess.run(
            [sys.executable, "-m", "travel_shared.seed_knowledge"],
            cwd=str(ROOT), env=self.env, capture_output=True, text=True,
            encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)

        custom = Path(self.env["TRAVEL_INTERNAL_DB"])
        self.assertTrue(custom.exists(), "seed 未写入 TRAVEL_INTERNAL_DB 指定路径")
        conn = sqlite3.connect(str(custom))
        try:
            steps = conn.execute("SELECT COUNT(*) FROM guided_questions").fetchone()[0]
            skills = conn.execute("SELECT COUNT(*) FROM skill_registry").fetchone()[0]
        finally:
            conn.close()
        self.assertGreaterEqual(steps, 12)
        self.assertEqual(skills, 9)

        default = self.home / ".travel-planner" / "internal.sqlite3"
        self.assertFalse(default.exists(), "seed 仍写入默认 HOME 位置")


if __name__ == "__main__":
    unittest.main()