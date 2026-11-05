# 12306-mcp 调用规程（嵌入 multi-platform-travel-planner）

本文件是 `map` 之外的铁路查询执行规范。`transport-research.md` 定义“必须核实什么”，本文件定义“具体怎么调、结果怎么落库”。

## 1. 前置能力检查

运行时可用工具中是否存在 MCP server `12306-mcp` 的以下工具：

- `get-current-date`
- `get-stations-code-in-city`
- `get-station-code-of-citys`
- `get-station-code-by-names`
- `get-station-by-telecode`
- `get-tickets`

**不存在时**按 `transport-research.md` 的降级顺序执行：浏览器打开官方 12306 页面 → 都不可用则 `lookup_status=tool_unavailable`，铁路段保持未知。不得用 OTA/地图/攻略的车次替代。

## 2. 固定调用序列

### 步骤 0：日期归一

用户说“明天/下周三/国庆”时，先调 `get-current-date` 取上海时区 `yyyy-MM-dd`，再换算目标日期。禁止用宿主本地时区或模型记忆猜日期。

### 步骤 1：车站解析

| 用户输入 | 工具 | 说明 |
|---|---|---|
| 城市名（“洛阳”） | `get-station-code-of-citys` | 取代表站；多城市用 `\|` 分隔 |
| 明确车站（“洛阳龙门”） | `get-station-code-by-names` | 精确到站 |
| 需要城市全部车站 | `get-stations-code-in-city` | 用户说“从洛阳哪个站都行”时用 |

城市级结果会包含该城市多个车站。**必须核对用户要的具体车站**；用户只说城市名且车站差异影响时间/费用时，先给候选车站再问一次（符合 `intake-and-output.md` 的地点歧义规则）。

### 步骤 2：余票查询

调 `get-tickets`：

| 参数 | 取值 |
|---|---|
| `date` | `yyyy-MM-dd` |
| `fromStation` | 中文站名或 `station_code` |
| `toStation` | 中文站名或 `station_code` |
| `trainFilterFlags` | 用户说“高铁”用 `G`；动车 `D`；不限留空 |
| `earliestStartTime` / `latestStartTime` | 0-24；用户给了时段就填，否则留 0/24 查全天 |
| `sortFlag` | `startTime` / `arriveTime` / `duration` |

去程和返程**各查一次**，都在同一轮完成，不要等用户催。用户未给可出发时段时：先查全天候选 → 展示 2-3 个可选时段 → 问用户确认 → 再定车次。不能默认清晨车次。

### 步骤 3：结果规范化

把 `get-tickets` 返回的文本经脚本转结构化，禁止手工摘录后凭记忆写票价：

```bash
python skills/multi-platform-travel-planner/scripts/normalize_railway_mcp.py \
  --file /tmp/12306_result.txt \
  --date 2026-11-10 --from 洛阳 --to 开封
```

或用 Python：

```python
from normalize_railway_mcp import normalize, choose_leg, to_route_segments
normalized = normalize(text, date="2026-11-10",
                        from_station="洛阳", to_station="开封")
leg = choose_leg(normalized, earliest="08:00", latest="12:00")
segment = to_route_segments(normalized, leg,
                            from_place_id="luoyanglongmen",
                            to_place_id="kaifengbei", date="2026-11-10")
```

脚本产出 `lookup_status`、`legs[]`（车次/站点/时刻/历时/席别/票价/余票）和 `evidence`。

## 3. lookup_status 判定

| 状态 | 条件 | 后续动作 |
|---|---|---|
| `verified` | 解析出至少一趟符合日期与站对的列车 | 可写具体车次、时刻、票价、余票，并标注来源与查询时间 |
| `no_result` | 工具正常返回但无匹配车次 | 写“该日期该站对无直达车”，可改查邻近站/中转 |
| `blocked` | 返回验证码/登录/限流字样 | 记录原因，降级浏览器或提示用户稍后重试 |
| `tool_unavailable` | 未安装 MCP、进程失败、空输出 | 铁路段全部 `unknown`，不得填占位车次 |
| `needs_station_clarification` | 城市名对应多个站且差异影响行程 | 列候选车站，问一个问题后重查 |

## 4. 写入下游契约

**路线时间线**（`validate_route_timeline.py`）：用 `to_route_segments()` 输出 `kind=transfer` 的 segment，含 `from_place_id`/`to_place_id`/`mode="rail"`、起止 ISO 时间、`train_no`、`duration_minutes`、`evidence`、`fare`。

**会话上下文**（Module B）：

```python
tools.handle({"action": "session_put", "trip_id": trip_id,
              "skill": "multi-platform-travel-planner",
              "stage": "verified", "key": "railway_legs",
              "value": session_payload(normalized)}, user_id=user_id)
```

下游 `travel-replanner`、`travel-plan-review`、`travel-time-pocket` 通过 `session_get` 读取 `railway_legs`，避免重复查询同一站对。

**证据记录**（必需字段）：`lookup_status`、`source="12306-mcp:get-tickets"`、`queried_at`（CST）、`date`、`requested_from`、`requested_to`、实际起终站。

## 5. 与结算口径

- 输出票价时附“以 12306 官方结算为准，余票和票价会变化”。
- 预算表把票价标为“已核实报价”，与估算项分开。
- 不使用 `候补` 状态作为“有票”；候补需单独提示风险。

## 6. 禁止事项

- 不登录、不填乘车人证件/手机号、不提交订单或支付、不自动改签。
- 不把 OTA、地图、攻略、搜索摘要当成车次/票价/余票证据。
- 不在日志或报告中写入乘车人身份信息。
- 工具失败时不得伪造车次或“已查询无车”。
- 同一失败路径最多重试一次，之后换源或返回 partial。