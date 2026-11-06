# 天气接入（官方 MCP + 免注册回退）

## 1. 两种接入方式

| 方式 | 类型 | 是否需要 key | 说明 |
|---|---|---|---|
| 彩云天气 | **官方 hosted MCP** | 需要（`CAIYUN_WEATHER_API_KEY`） | 彩云官方维护，Streamable HTTP，国内稳定 |
| Open-Meteo | 免费公开 API | 不需要 | 无需注册，直接 HTTP；作为默认回退 |

## 2. 方式一：彩云天气官方 MCP

1. 到 <https://platform.caiyunapp.com> 注册并申请 API key。
2. 在宿主 MCP 配置中加入：

```json
{
  "mcpServers": {
    "caiyun-weather": {
      "url": "https://mcp-weather.caiyunapp.com/mcp",
      "headers": {
        "X-Caiyun-API-Key": "<YOUR_CAIYUN_WEATHER_API_KEY>"
      }
    }
  }
}
```

3. 自检：

```bash
export CAIYUN_WEATHER_API_KEY=你的key
python scripts/check_weather.py --provider caiyun
# status: configured
```

`status=not_configured` 时脚本会打印申请地址与配置模板，退出码 2。

## 3. 方式二：Open-Meteo（免注册回退）

```bash
python scripts/check_weather.py --city 贵阳 --days 3
python scripts/check_weather.py --lat 26.65 --lon 106.63 --json
```

实测（2026-11-06）：

```
来源: open-meteo.com 查询时间: 2026-11-06T10:36:45+08:00
贵阳 当前 14.5°C 阴
  2026-11-06 11.2~19.0°C 降水概率 100% 毛毛雨
  2026-11-07 12.1~17.5°C 降水概率 84% 小阵雨
  2026-11-08 6.7~16.4°C 降水概率 100% 雷阵雨
```

内置城市坐标：贵阳、开封、洛阳、成都、重庆、西安、杭州、南京、北京、长沙；其他城市用 `--lat/--lon`，或补充 `scripts/check_weather.py` 的 `CITY_COORDS`。

## 4. 运行时优先级（已写进 skill 规程）

1. 宿主已安装彩云天气 MCP → 调用其工具；
2. 否则运行 `scripts/check_weather.py`（Open-Meteo）；
3. 都不可用 → 浏览器检索官方气象源；
4. 仍失败 → 标记 `unknown`，不编造天气。

任何来源都必须记录 `source`、`queried_at`、温度区间与降水概率；预报变化快，报告中提示出行前复查。

## 5. 边界

- Open-Meteo 是国际公开数据，中国区精度与官方气象台可能有差异；涉及暴雨/台风等预警必须以中国气象局/当地气象台为准。
- 彩云 MCP 是官方 hosted 服务，但 key 与额度由你的账号决定。
- 天气只用于行程取舍与雨天备选，不替代景区开放公告。