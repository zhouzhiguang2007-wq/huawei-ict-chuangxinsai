"""Regression checks for the downloadable plugin package."""

import copy
import json
import unittest
from pathlib import Path

from scripts.validate_plugin_manifest import validate_manifest, validate_manifest_data


ROOT = Path(__file__).resolve().parents[1]


class PluginManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))

    def test_checkout_manifest_is_complete(self):
        self.assertEqual(validate_manifest(ROOT), [])

    def test_unknown_orchestration_skill_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data["orchestration"]["main_flow"].append("missing-skill")
        self.assertTrue(any("unknown skill" in error for error in validate_manifest_data(data, ROOT)))

    def test_missing_schema_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data["$schema"] = "./absent.schema.json"
        self.assertTrue(any("$schema" in error for error in validate_manifest_data(data, ROOT)))

    def test_paths_cannot_escape_package(self):
        data = copy.deepcopy(self.manifest)
        data["shared_tools"]["openapi"] = "../outside.json"
        self.assertTrue(any("shared_tools.openapi" in error for error in validate_manifest_data(data, ROOT)))

    def test_invalid_agent_and_boolean_top_k_are_rejected(self):
        data = copy.deepcopy(self.manifest)
        data["agent"] = "../../other"
        data["rag"]["top_k"] = True
        errors = validate_manifest_data(data, ROOT)
        self.assertTrue(any("agent must be a safe name" in error for error in errors))
        self.assertTrue(any("rag.top_k" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
