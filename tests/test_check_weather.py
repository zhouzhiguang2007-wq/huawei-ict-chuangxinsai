"""天气自检脚本测试（纯函数 + 参数校验，不联网）。

unittest 风格，CI 可直接运行。
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import check_weather  # noqa: E402

SAMPLE = {
    "current": {"temperature_2m": 14.5, "weather_code": 3},
    "daily": {
        "time": ["2026-11-06", "2026-11-07", "2026-11-08", "2026-11-09"],
        "temperature_2m_max": [19.0, 17.5, 16.4, 18.0],
        "temperature_2m_min": [11.2, 12.1, 6.7, 8.0],
        "precipitation_probability_max": [100, 84, 100, 20],
        "weather_code": [3, 61, 63, 0],
    },
}


class ResolveCityTest(unittest.TestCase):

    def test_known_city(self):
        self.assertEqual(check_weather.resolve_city("贵阳"), (26.65, 106.63))

    def test_unknown_city(self):
        self.assertIsNone(check_weather.resolve_city("不存在的城市"))

    def test_weather_text(self):
        self.assertEqual(check_weather.weather_text(0), "晴")
        self.assertEqual(check_weather.weather_text(61), "小雨")
        self.assertIn("未知天气", check_weather.weather_text(999))


class BuildReportTest(unittest.TestCase):

    def test_report_fields(self):
        report = check_weather.build_report(
            SAMPLE, "贵阳", 26.65, 106.63,
            queried_at="2026-11-06T08:00:00+08:00", days=3)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["source"], "open-meteo.com")
        self.assertEqual(report["current"]["temp_c"], 14.5)
        self.assertEqual(report["current"]["weather"], "阴")
        self.assertEqual(len(report["daily"]), 3)
        self.assertEqual(report["daily"][0]["date"], "2026-11-06")
        self.assertEqual(report["daily"][0]["precip_prob_max"], 100)

    def test_report_respects_days_limit(self):
        report = check_weather.build_report(SAMPLE, "贵阳", 0, 0, days=2)
        self.assertEqual(len(report["daily"]), 2)

    def test_missing_fields_are_null(self):
        report = check_weather.build_report({}, "贵阳", 0, 0, days=3)
        self.assertIsNone(report["current"]["temp_c"])
        self.assertEqual(report["daily"], [])


class CliTest(unittest.TestCase):

    def test_no_args_returns_two(self):
        self.assertEqual(check_weather.main([]), 2)

    def test_unknown_city_returns_two(self):
        self.assertEqual(check_weather.main(["--city", "不存在的城市"]), 2)

    def test_caiyun_without_key_returns_two(self):
        env = dict(os.environ)
        env.pop("CAIYUN_WEATHER_API_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(check_weather.main(["--provider", "caiyun"]), 2)

    def test_caiyun_with_key_returns_zero(self):
        with patch.dict(os.environ, {"CAIYUN_WEATHER_API_KEY": "demo-key"}):
            self.assertEqual(check_weather.main(["--provider", "caiyun"]), 0)


if __name__ == "__main__":
    unittest.main()