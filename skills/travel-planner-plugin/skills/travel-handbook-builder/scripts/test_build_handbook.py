"""Check source validation, safe rendering, and offline fallback."""

import json
from pathlib import Path
import tempfile
import unittest

from build_handbook import build

TEST_ROOT = Path(__file__).resolve().parents[1]


class HandbookTests(unittest.TestCase):
    def sample(self):
        return {
            "title": "演示 <script>alert(1)</script>",
            "destination": "示例城",
            "review_status": "draft",
            "days": [{"date": "2026-11-01", "title": "第一天", "stops": [
                {"id": "stop-one", "name": "无坐标景点", "description": "保留在时间线"}
            ]}],
            "places": [{"name": "无坐标景点", "photo": {
                "path": "private.png", "reuse_allowed": False,
                "source_url": "https://example.org/photo", "note": "仅给原页链接"
            }}],
        }

    def test_unverified_location_and_private_photo_stay_out_of_map_and_bundle(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as raw:
            root = Path(raw)
            self.assertTrue(root.resolve().is_relative_to(TEST_ROOT))
            path = root / "plan.json"
            path.write_text(json.dumps(self.sample(), ensure_ascii=False), encoding="utf-8")
            build(path, root / "out")
            route = (root / "out/route.html").read_text(encoding="utf-8")
            places = (root / "out/places.html").read_text(encoding="utf-8")
            index = (root / "out/index.html").read_text(encoding="utf-8")
            self.assertIn("无坐标景点", route)
            self.assertIn("没有经核实的坐标", route)
            self.assertNotIn("<svg", route)
            self.assertNotIn("private.png", places)
            self.assertFalse((root / "out/media").exists())
            self.assertIn("&lt;script&gt;", index)
            self.assertNotIn("<script>alert(1)</script>", index)

    def test_coordinate_without_source_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as raw:
            root = Path(raw)
            self.assertTrue(root.resolve().is_relative_to(TEST_ROOT))
            data = self.sample()
            data["days"][0]["stops"][0].update({
                "latitude": 30.0, "longitude": 114.0,
                "coordinate_system": "WGS84", "coordinate_kind": "示意点"
            })
            path = root / "plan.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "coordinate_source_url"):
                build(path, root / "out")
            self.assertFalse((root / "out").exists())

    def test_shareable_photo_cannot_escape_input_folder(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as raw:
            root = Path(raw)
            self.assertTrue(root.resolve().is_relative_to(TEST_ROOT))
            data = self.sample()
            data["places"][0]["photo"].update({"path": "../other.png", "reuse_allowed": True, "rights_note": "用户本人拍摄"})
            path = root / "plan.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "相对路径"):
                build(path, root / "out")
            self.assertFalse((root / "out/index.html").exists())

    def test_shareable_photo_requires_rights_basis(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as raw:
            root = Path(raw)
            self.assertTrue(root.resolve().is_relative_to(TEST_ROOT))
            data = self.sample()
            data["places"][0]["photo"].update({"path": "photo.png", "reuse_allowed": True})
            path = root / "plan.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "rights_note"):
                build(path, root / "out")


if __name__ == "__main__":
    unittest.main()
