"""插件打包测试：内容齐全、排除缓存与本地库。

unittest 风格，CI 可直接运行。
"""

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import export_plugin  # noqa: E402


class ExportPluginTest(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name) / "plugin.zip"

    def tearDown(self):
        self.temp.cleanup()

    def build(self, include_rag_index=False):
        report = export_plugin.build(self.output, include_rag_index)
        with zipfile.ZipFile(self.output) as archive:
            names = set(archive.namelist())
        return report, names

    def test_contains_manifest_and_skills(self):
        report, names = self.build()
        self.assertIn("plugin.json", names)
        self.assertIn("plugin.schema.json", names)
        self.assertIn("agents/travel-planner.md", names)
        self.assertIn("travel_shared/tools.py", names)
        self.assertIn("skills/travel-planner-plugin/SKILL.md", names)
        self.assertGreater(report["file_count"], 50)

    def test_excludes_cache_and_local_databases(self):
        _, names = self.build()
        for name in names:
            self.assertNotIn("__pycache__", name)
            self.assertNotIn(".pytest_cache", name)
            self.assertFalse(name.endswith(".pyc"), name)
            self.assertFalse(name.endswith(".sqlite3"), name)
            self.assertFalse(name.startswith(".git/"), name)

    def test_excludes_rag_index_by_default(self):
        _, names = self.build()
        self.assertFalse(any(n.startswith("rag/index/") for n in names))

    def test_can_include_rag_index(self):
        _, names = self.build(include_rag_index=True)
        self.assertTrue(any(n.startswith("rag/index/") for n in names))

    def test_report_includes_manifest_version(self):
        report, _ = self.build()
        import json
        manifest = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(report["version"], manifest["version"])


if __name__ == "__main__":
    unittest.main()