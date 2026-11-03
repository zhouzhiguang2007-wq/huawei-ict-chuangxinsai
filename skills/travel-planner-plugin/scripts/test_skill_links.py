"""Keep plugin entrypoints linked to the shared contract in a full checkout."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
LINK = re.compile(r"\]\(([^)]+)\)")


class SkillLinkTests(unittest.TestCase):
    def test_local_markdown_links_resolve_in_full_repository(self):
        checked = 0
        for source in sorted((ROOT / "skills").rglob("*.md")):
            for link in LINK.findall(source.read_text(encoding="utf-8-sig")):
                if link.startswith(("http://", "https://", "mailto:", "#", "/")) or "://" in link:
                    continue
                target = (source.parent / link.split("#", 1)[0]).resolve()
                with self.subTest(source=source.relative_to(ROOT), link=link):
                    self.assertTrue(target.is_file(), "Broken local Markdown link")
                checked += 1
        self.assertGreater(checked, 0)

    def test_all_nine_skills_share_one_contract(self):
        entrypoints = sorted((ROOT / "skills").glob("*/SKILL.md"))
        self.assertEqual(len(entrypoints), 9)
        contract = (ROOT / "docs" / "shared-interface.md").resolve()
        for source in entrypoints:
            links = [link for link in LINK.findall(source.read_text(encoding="utf-8-sig"))
                     if link.endswith("docs/shared-interface.md")]
            with self.subTest(skill=source.parent.name):
                self.assertEqual(len(links), 1)
                self.assertEqual((source.parent / links[0]).resolve(), contract)


if __name__ == "__main__":
    unittest.main()
