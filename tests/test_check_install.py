"""安装自检测试：全目录比对、差异与未安装检测。

unittest 风格，CI 可直接运行。
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import check_install  # noqa: E402


def copy_skills(target):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    for skill in check_install.load_manifest(ROOT)[1]:
        shutil.copytree(
            ROOT / "skills" / skill, target / skill,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return target


class CheckInstallTest(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.install = copy_skills(Path(self.temp.name) / "skills")

    def tearDown(self):
        self.temp.cleanup()

    def test_all_same(self):
        version, comparisons = check_install.check(self.install)
        problems = [c for c in comparisons if c[2] != "same"]
        self.assertEqual(problems, [])
        self.assertEqual(version, "0.3.0")

    def test_detects_content_diff(self):
        target = self.install / "x-xiake" / "SKILL.md"
        target.write_text(target.read_text(encoding="utf-8") + "\n# drift\n",
                          encoding="utf-8")
        _, comparisons = check_install.check(self.install)
        diffs = [c for c in comparisons if c[2] == "diff"]
        self.assertTrue(any(c[0] == "x-xiake" and c[1] == "SKILL.md" for c in diffs))

    def test_detects_reference_drift(self):
        refs_dir = self.install / "travel-plan-review" / "references"
        ref = sorted(refs_dir.glob("*.md"))[0]
        ref.write_text(ref.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
        _, comparisons = check_install.check(self.install)
        diffs = [c for c in comparisons if c[2] == "diff"]
        self.assertTrue(any(c[0] == "travel-plan-review" for c in diffs))

    def test_detects_missing_skill(self):
        shutil.rmtree(self.install / "travel-time-pocket")
        _, comparisons = check_install.check(self.install)
        missing = [c for c in comparisons if c[2] == "missing_install"]
        self.assertTrue(any(c[0] == "travel-time-pocket" for c in missing))

    def test_cli_exit_codes(self):
        with patch.object(check_install, "DEFAULT_INSTALL_DIRS", (Path(self.temp.name) / "absent",)):
            self.assertEqual(check_install.main([]), 2)
        self.assertEqual(check_install.main([str(self.install)]), 0)
        target = self.install / "x-xiake" / "SKILL.md"
        target.write_text("drift", encoding="utf-8")
        self.assertEqual(check_install.main([str(self.install)]), 1)

    def test_cli_uses_first_existing_default_install(self):
        absent = Path(self.temp.name) / "absent"
        with patch.object(check_install, "DEFAULT_INSTALL_DIRS", (absent, self.install)):
            self.assertEqual(check_install.main([]), 0)


if __name__ == "__main__":
    unittest.main()
