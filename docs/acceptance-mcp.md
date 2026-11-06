# MCP 联调验收记录（12306）

本文件记录铁路 MCP 的自检方式与实测结果，用于比赛现场确认“工具真的能起来、能列出来、能返回真实车次”。

## 1. 自检脚本

```bash
python scripts/check_mcp.py            # 启动并握手，核对必需工具
python scripts/check_mcp.py --json     # 机器可读输出
python scripts/check_mcp.py --skip-network   # 只检查 npx/Node 是否可用
```

退出码：`0` 可用；`1` 工具缺失或握手失败；`2` 找不到命令（Node.js 18+ 未装）。

必需工具：`get-current-date`、`get-stations-code-in-city`、`get-station-code-of-citys`、`get-station-code-by-names`、`get-station-by-telecode`、`get-tickets`。

## 2. 本次实测结果（2026-11-06）

```
命令: npx -y 12306-mcp
状态: ok
服务端: 12306-mcp 0.3.10
工具数: 8
工具: get-current-date, get-stations-code-in-city, get-station-code-of-citys,
      get-station-code-by-names, get-station-by-telecode, get-tickets,
      get-interline-tickets, get-train-route-stations
缺少工具: 无
退出码: 0
```

真实余票查询（2026-11-05 实测，查询 2026-11-10 洛阳→开封）：

```
G1812 洛阳龙门 08:05 -> 开封北 09:12 历时 01:07  二等座 有票 91 元
G2260 洛阳龙门 11:16 -> 开封北 12:19 历时 01:03  二等座 有票 91 元
G1880 洛阳龙门 18:04 -> 开封北 19:05 历时 01:01  二等座 有票 80 元
```

结果经 `skills/multi-platform-travel-planner/scripts/normalize_railway_mcp.py` 解析为结构化 legs，`lookup_status=verified`。

## 3. 其他实时资料的验收状态

| 资料 | 连接方式 | 当前状态 | 降级行为 |
|---|---|---|---|
| 铁路车次/余票/票价 | 12306-mcp（社区实现） | ✅ 本地自检通过；宿主内需在「设置 > MCP 工具」添加后人工确认一次 | 浏览器打开官方 12306 → 仍不可用则 `tool_unavailable`，铁路段标未知 |
| 地图/POI/接驳 | 高德 MCP（宿主提供，可选） | ⚠️ 依赖宿主是否已安装高德 MCP，仓库不自带 | 用公开地图网页核实并记录来源与时间 |
| 天气 | 无专用 MCP | ⚠️ 仅网页检索 | 记录来源与查询时间；无数据时标 `unknown` |
| 住宿报价 | 无官方 MCP | ⚠️ 仅网页检索；`docs` 明确不假定平台有 MCP | 标“待销售渠道核实”，不伪造总价 |

## 4. 仍需人工完成的验收

以下两项无法由仓库脚本自动化，需在码道 / AgentArts 控制台完成并留证：

1. 在「设置 > MCP 工具」添加 `12306-mcp` 配置，重启/刷新自定义智能体，发一句「帮我查 2026-11-10 洛阳到开封的高铁」，截图保存调用详情（工具名、入参、返回）。
2. 天气与住宿各做一次真实页面查询，记录 URL、查询时间与来源，确认降级文案生效。

配置 JSON：

```json
{"mcpServers": {"12306-mcp": {"command": "npx", "args": ["-y", "12306-mcp"]}}}
```

## 5. 边界

- `12306-mcp` 是社区实现，读取官方页面数据，不是官方 API；结果必须标注来源与查询时间，支付前以 12306 官方为准。
- 不登录、不填乘车人证件、不提交订单或支付。
- 工具失效时不得伪造车次；`lookup_status` 只能取实测值。