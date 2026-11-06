"""The CI gate rejects malformed plugin JSON before deployment."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import run_checks  # noqa: E402


class JsonSyntaxChecksTest(unittest.TestCase):
    def test_both_json_files_are_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "plugin.json").write_text("{}", encoding="utf-8")
            (root / "plugin.schema.json").write_text("{", encoding="utf-8")
            errors = run_checks.check_json_files(root)
            self.assertEqual(len(errors), 1)
            self.assertTrue(errors[0].startswith("plugin.schema.json:"))

            (root / "plugin.json").write_text("[", encoding="utf-8")
            errors = run_checks.check_json_files(root)
            self.assertEqual(len(errors), 2)


if __name__ == "__main__":
    unittest.main()
