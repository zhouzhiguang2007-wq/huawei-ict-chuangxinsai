"""skill 关系图一致性测试。

保证 docs/skill-map.md 与 plugin.json + seed 注册表一致，避免文档漂移。
unittest 风格，CI 可直接运行。
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import render_skill_map  # noqa: E402


class SkillMapTest(unittest.TestCase):

    def setUp(self):
        self.manifest = json.loads(
            (ROOT / "plugin.json").read_text(encoding="utf-8"))

    def test_document_matches_generator(self):
        generated = render_skill_map.render(self.manifest)
        on_disk = (ROOT / "docs" / "skill-map.md").read_text(encoding="utf-8")
        self.assertEqual(on_disk, generated,
                         "docs/skill-map.md 与生成结果不一致，请运行 "
                         "python scripts/render_skill_map.py")

    def test_graph_nodes_match_manifest_skills(self):
        graph = self.manifest["skill_graph"]
        self.assertEqual(set(graph["nodes"]), set(self.manifest["skills"]))

    def test_edges_reference_known_nodes(self):
        nodes = set(self.manifest["skill_graph"]["nodes"])
        for edge in self.manifest["skill_graph"]["edges"]:
            self.assertIn(edge["from"], nodes)
            self.assertIn(edge["to"], nodes)

    def test_every_skill_has_trigger_keywords(self):
        from travel_shared.seed_knowledge import SKILL_REGISTRY_DATA
        registry = {e["skill_name"]: e for e in SKILL_REGISTRY_DATA}
        for skill in self.manifest["skills"]:
            self.assertIn(skill, registry, "注册表缺少 " + skill)
            self.assertTrue(registry[skill].get("trigger_keywords"))

    def test_orchestrator_reaches_post_delivery_skills(self):
        edges = self.manifest["skill_graph"]["edges"]
        targets = {e["to"] for e in edges if e["from"] == "travel-planner-plugin"}
        self.assertIn("travel-replanner", targets)
        self.assertIn("travel-time-pocket", targets)

    def test_deployment_and_acceptance_documents_exist(self):
        for key in ("guide",):
            self.assertTrue((ROOT / self.manifest["deployment"][key]).exists())
        for key in ("e2e", "mcp", "manual", "demo"):
            self.assertTrue((ROOT / self.manifest["acceptance"][key]).exists(),
                            "缺少验收文档: " + key)


if __name__ == "__main__":
    unittest.main()