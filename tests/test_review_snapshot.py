"""防止 review 引擎快照漂移。

`travel-replanner` 随包携带一份 review 校验器快照（`_review_engine.py`），
以便单独加载该 skill 时不必依赖 `travel-plan-review`。快照必须与主实现
`travel-plan-review/scripts/validate_itinerary.py` 完全一致；若只改了一边，
两个 skill 的校验结果会悄悄分叉。

unittest 风格，CI 的 unittest discover 可直接运行；无第三方依赖。
"""

import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "skills" / "travel-plan-review" / "scripts" / "validate_itinerary.py"
SNAPSHOT = ROOT / "skills" / "travel-replanner" / "scripts" / "_review_engine.py"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReviewSnapshotTest(unittest.TestCase):

    def test_both_files_exist(self):
        self.assertTrue(MAIN.is_file(), "缺少主实现 validate_itinerary.py")
        self.assertTrue(SNAPSHOT.is_file(), "缺少快照 _review_engine.py")

    def test_snapshot_matches_main_validator(self):
        self.assertEqual(
            sha256(SNAPSHOT), sha256(MAIN),
            "review 引擎快照已漂移：travel-replanner/scripts/_review_engine.py "
            "与 travel-plan-review/scripts/validate_itinerary.py 不一致。"
            "请以主实现为准重新复制快照，并同步 references/review-integration.md 的来源说明。",
        )


if __name__ == "__main__":
    unittest.main()