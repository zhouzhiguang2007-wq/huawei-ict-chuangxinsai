"""天气能力自检与预报获取。

两种接入方式：
1. `open-meteo`（默认，免费、无需 key）：直接拉取当前天气与未来 N 天预报；
2. `caiyun`（彩云天气官方 hosted MCP）：只检查 API key 是否就绪并输出宿主
   配置，实际调用由宿主 MCP 完成。

用法：
    python scripts/check_weather.py --city 贵阳
    python scripts/check_weather.py --lat 26.65 --lon 106.63
    python scripts/check_weather.py --city 贵阳 --days 5 --json
    python scripts/check_weather.py --provider caiyun

退出码：0 成功/已配置；1 获取失败；2 参数或 key 缺失。
纯标准库，Python 3.9+。
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
CAIYUN_MCP_URL = "https://mcp-weather.caiyunapp.com/mcp"

# 常用城市中心坐标（可继续补充）
CITY_COORDS = {
    "贵阳": (26.65, 106.63),
    "开封": (34.80, 114.31),
    "洛阳": (34.62, 112.45),
    "成都": (30.57, 104.07),
    "重庆": (29.56, 106.55),
    "西安": (34.34, 108.94),
    "杭州": (30.27, 120.16),
    "南京": (32.06, 118.80),
    "北京": (39.90, 116.41),
    "长沙": (28.23, 112.94),
}

# WMO weather code -> 中文
WMO_TEXT = {
    0: "晴", 1: "多云间晴", 2: "多云", 3: "阴",
    45: "雾", 48: "雾凇",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    56: "冻毛毛雨", 57: "强冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "强冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "小阵雨", 81: "阵雨", 82: "强阵雨",
    85: "小阵雪", 86: "强阵雪",
    95: "雷阵雨", 96: "雷阵雨伴冰雹", 99: "强雷暴",
}


def resolve_city(name):
    """城市名 -> (lat, lon)；未知返回 None。"""
    return CITY_COORDS.get((name or "").strip())


def weather_text(code):
    return WMO_TEXT.get(code, "未知天气({})".format(code))


def build_report(payload, city, lat, lon, provider="open-meteo",
                 queried_at=None, days=3):
    """把 Open-Meteo 响应转为统一结构（纯函数，便于测试）。"""
    current = payload.get("current", {})
    daily = payload.get("daily", {})
    dates = daily.get("time", [])
    report_daily = []
    for index, day in enumerate(dates[:days]):
        report_daily.append({
            "date": day,
            "max_c": _pick(daily.get("temperature_2m_max"), index),
            "min_c": _pick(daily.get("temperature_2m_min"), index),
            "precip_prob_max": _pick(daily.get("precipitation_probability_max"), index),
            "weather": weather_text(_pick(daily.get("weather_code"), index)),
        })
    if queried_at is None:
        queried_at = datetime.now(CST).isoformat(timespec="seconds")
    return {
        "status": "ok",
        "provider": provider,
        "source": "open-meteo.com",
        "city": city,
        "lat": lat,
        "lon": lon,
        "queried_at": queried_at,
        "current": {
            "temp_c": current.get("temperature_2m"),
            "weather": weather_text(current.get("weather_code")),
            "code": current.get("weather_code"),
        },
        "daily": report_daily,
        "note": "天气会变化；出行前请再次查询，并在报告中标注来源与查询时间。",
    }


def _pick(values, index):
    if not values or index >= len(values):
        return None
    return values[index]


def fetch_open_meteo(lat, lon, days=3, timeout=20):
    query = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,"
                 "precipitation_probability_max,weather_code",
        "timezone": "Asia/Shanghai",
        "forecast_days": max(1, min(days, 16)),
    })
    with urllib.request.urlopen(OPEN_METEO_URL + "?" + query, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def check_caiyun():
    """彩云天气官方 hosted MCP：只检查 key 与配置，不发起调用。"""
    key = os.environ.get("CAIYUN_WEATHER_API_KEY", "").strip()
    if not key:
        return {
            "status": "not_configured",
            "provider": "caiyun",
            "message": "未设置 CAIYUN_WEATHER_API_KEY",
            "fix": "到 https://platform.caiyunapp.com 申请 key，并在宿主 MCP 配置中设置",
            "mcp_config": {
                "url": CAIYUN_MCP_URL,
                "headers": {"X-Caiyun-API-Key": "<YOUR_CAIYUN_WEATHER_API_KEY>"},
            },
        }
    return {
        "status": "configured",
        "provider": "caiyun",
        "message": "彩云天气 key 已配置；实际预报由宿主 MCP 调用",
        "mcp_config": {"url": CAIYUN_MCP_URL,
                       "headers": {"X-Caiyun-API-Key": "***"}},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="天气能力自检与预报")
    parser.add_argument("--city", default=None)
    parser.add_argument("--lat", type=float, default=None)
    parser.add_argument("--lon", type=float, default=None)
    parser.add_argument("--provider", choices=("open-meteo", "caiyun"),
                        default="open-meteo")
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--json", dest="as_json", action="store_true")
    args = parser.parse_args(argv)

    if args.provider == "caiyun":
        result = check_caiyun()
        if args.as_json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("provider:", result["provider"])
            print("status:", result["status"])
            print(result["message"])
            if result["status"] != "configured":
                print("fix:", result["fix"])
                print("mcp:", json.dumps(result["mcp_config"], ensure_ascii=False))
        return 0 if result["status"] == "configured" else 2

    lat, lon = args.lat, args.lon
    if lat is None or lon is None:
        if not args.city:
            print("用法：--city <城市> 或同时提供 --lat 与 --lon")
            return 2
        coords = resolve_city(args.city)
        if coords is None:
            print("未知城市：{}；请改用 --lat/--lon，或补充 CITY_COORDS".format(args.city))
            return 2
        lat, lon = coords

    try:
        payload = fetch_open_meteo(lat, lon, days=args.days)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print("天气获取失败：{}".format(exc))
        return 1

    report = build_report(payload, args.city or "{},{}".format(lat, lon),
                          lat, lon, days=args.days)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("来源:", report["source"], "查询时间:", report["queried_at"])
        print("{} 当前 {}°C {}".format(report["city"], report["current"]["temp_c"],
                                       report["current"]["weather"]))
        for day in report["daily"]:
            print("  {} {}~{}°C 降水概率 {}% {}".format(
                day["date"], day["min_c"], day["max_c"],
                day["precip_prob_max"], day["weather"]))
        print(report["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())