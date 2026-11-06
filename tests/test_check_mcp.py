"""check_mcp 纯函数测试（不启动网络/子进程）。

覆盖 `evaluate_tools` 的齐全/缺失判定，以及 CLI 参数解析的默认值。
unittest 风格，CI 可直接运行。
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import check_mcp  # noqa: E402


ALL_TOOLS = list(check_mcp.REQUIRED_TOOLS) + ["extra-tool"]


class EvaluateToolsTest(unittest.TestCase):

    def test_all_required_present(self):
        result = check_mcp.evaluate_tools(ALL_TOOLS)
        self.assertTrue(result["ok"])
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["tool_count"], len(ALL_TOOLS))

    def test_missing_tool_detected(self):
        tools = [t for t in ALL_TOOLS if t != "get-tickets"]
        result = check_mcp.evaluate_tools(tools)
        self.assertFalse(result["ok"])
        self.assertEqual(result["missing"], ["get-tickets"])

    def test_empty_tools_all_missing(self):
        result = check_mcp.evaluate_tools([])
        self.assertFalse(result["ok"])
        self.assertEqual(result["missing"], list(check_mcp.REQUIRED_TOOLS))

    def test_required_list_matches_documented_tools(self):
        for name in ("get-current-date", "get-station-code-by-names",
                     "get-station-code-of-citys", "get-tickets"):
            self.assertIn(name, check_mcp.REQUIRED_TOOLS)


class CliSkipNetworkTest(unittest.TestCase):

    def test_skip_network_returns_two_when_command_missing(self):
        code = check_mcp.main(["--command", "definitely-not-a-real-command-xyz",
                               "--skip-network"])
        self.assertEqual(code, 2)

    def test_skip_network_ok_when_command_exists(self):
        import shutil
        if not shutil.which("python"):
            self.skipTest("python 不在 PATH")
        code = check_mcp.main(["--command", "python", "--skip-network"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()