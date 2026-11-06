"""端到端闭环 smoke 的 CI 测试。

证明「seed → 问卷 → 注册表 → 知识 → 会话 → 铁路解析 → 路线校验 → prepare」
在临时库上可跑通。真实宿主对话验收仍需人工完成。
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import e2e_smoke  # noqa: E402


class E2ESmokeTest(unittest.TestCase):

    def test_all_steps_pass(self):
        ok, steps = e2e_smoke.run()
        failed = [s for s in steps if not s["ok"]]
        self.assertTrue(ok, "失败步骤: {}".format(failed))
        self.assertGreaterEqual(len(steps), 10)

    def test_route_validation_passes(self):
        ok, steps = e2e_smoke.run()
        route_step = next(s for s in steps if s["step"] == "route.validate")
        self.assertTrue(route_step["ok"])
        self.assertEqual(route_step["detail"]["status"], "pass")

    def test_cli_exit_zero(self):
        self.assertEqual(e2e_smoke.main([]), 0)


if __name__ == "__main__":
    unittest.main()