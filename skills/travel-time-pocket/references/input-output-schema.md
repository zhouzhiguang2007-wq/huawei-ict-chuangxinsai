# 输入输出契约

## AgentArts 代码节点

输入参数：

| 名称 | 类型 | 说明 |
|---|---|---|
| `pocket_json` | String | 下述计算输入对象序列化后的 JSON 字符串 |

输出参数：

| 名称 | 类型 | 说明 |
|---|---|---|
| `status` | String | `feasible`、`incomplete`、`infeasible` 或 `invalid` |
| `report_json` | String | 完整计算报告序列化后的 JSON 字符串 |

## 计算输入对象

所有时间必须是带 UTC 偏移的 ISO 8601 日期时间。路线时间应对应当前时段和指定交通方式。

```json
{
  "schema_version": "1.1",
  "current_time": "2026-11-01T16:00:00+08:00",
  "must_return_by": "2026-11-01T19:00:00+08:00",
  "origin": "甲秀楼",
  "origin_place_id": "amap-origin-id",
  "return_to": "贵阳北站",
  "return_place_id": "amap-return-id",
  "departure_preparation_minutes": 10,
  "buffer_minutes": 25,
  "route_policy": {
    "require_status": true,
    "require_queried_at": true,
    "max_age_minutes": 30
  },
  "candidates": [
    {
      "id": "c1",
      "name": "贵州省民族博物馆",
      "place_id": "amap-candidate-id",
      "outbound_route": {
        "availability": "available",
        "duration_minutes": 20,
        "queried_at": "2026-11-01T16:00:00+08:00"
      },
      "queue_minutes": 10,
      "minimum_visit_minutes": 60,
      "return_route": {
        "availability": "available",
        "duration_minutes": 35,
        "queried_at": "2026-11-01T16:01:00+08:00"
      },
      "available": true,
      "always_open": false,
      "latest_entry": "2026-11-01T17:00:00+08:00",
      "opening_windows": [
        {
          "start": "2026-11-01T09:00:00+08:00",
          "end": "2026-11-01T18:00:00+08:00"
        }
      ],
      "cost": {"amount": 0, "currency": "CNY"},
      "evidence": [
        {"field": "route", "source": "map_mcp", "queried_at": "2026-11-01T16:00:00+08:00"},
        {"field": "opening", "source": "official", "queried_at": "2026-11-01T16:01:00+08:00"}
      ]
    }
  ]
}
```

字段规则：

- `departure_preparation_minutes` 表示从收到请求到真正出发所需的收拾、下楼或集合时间；不能默认用户能瞬间出发。
- `buffer_minutes`、路线、准备、排队和游玩分钟数必须为非负整数；`minimum_visit_minutes` 应大于0。
- `outbound_route` 和 `return_route` 应直接使用地图 MCP 在当前交通方式、当前时段下返回的结果。`availability` 只能为 `available`、`unavailable` 或 `unknown`。
- 路线为 `available` 时必须提供 `duration_minutes`；`unavailable` 直接判为不可行；`unknown` 或缺失耗时判为信息不完整。
- 1.1 输入默认要求路线状态和 `queried_at`。路线数据超过 `route_policy.max_age_minutes`、缺少查询时间，或不同地点间出现零分钟路线时，只能判为 `incomplete`，应重新查询后再推荐。
- `origin_place_id`、`return_place_id`、`place_id` 优先使用地图平台的稳定 POI ID，用来识别“同一地点”和拦截异常零分钟路线。
- `available=true` 表示已确认当前可用，`false` 表示明确不可用，`null` 表示未知。
- 全天无需营业时间约束的地点设置 `always_open=true`；否则提供至少一个 `opening_windows`。
- 开放窗口的 `end` 是最晚完成活动时间；已知停止入场时间时另外填写 `latest_entry`，两项约束会同时检查。
- `evidence` 记录来源，不由计算脚本判断来源真实性。
- 候选的天气、体力、兴趣和预算筛选应在进入脚本前完成，或作为上游警告保留；代码只负责确定性时间约束。

旧版 `travel_to_minutes`、`travel_back_minutes` 仍可在 `schema_version=1.0` 下使用，便于旧工作流迁移；报告会给出 `legacy` 警告。新工作流应使用 1.1 路线对象。

## 计算报告

```json
{
  "status": "feasible",
  "schema_version": "1.1",
  "window_minutes": 180,
  "usable_minutes": 170,
  "departure_preparation_minutes": 10,
  "buffer_minutes": 25,
  "candidates": [
    {
      "id": "c1",
      "name": "贵州省民族博物馆",
      "status": "feasible",
      "departure_time": "2026-11-01T16:10:00+08:00",
      "arrival_time": "2026-11-01T16:30:00+08:00",
      "activity_start_time": "2026-11-01T16:40:00+08:00",
      "activity_end_time": "2026-11-01T17:40:00+08:00",
      "return_time": "2026-11-01T18:15:00+08:00",
      "safe_return_time": "2026-11-01T18:40:00+08:00",
      "spare_minutes": 20,
      "duration_breakdown": {
        "travel_to_minutes": 20,
        "queue_minutes": 10,
        "opening_wait_minutes": 0,
        "visit_minutes": 60,
        "travel_back_minutes": 35,
        "buffer_minutes": 25,
        "total_after_departure_minutes": 150
      },
      "reason_codes": [],
      "reasons": []
    }
  ],
  "errors": []
}
```

`safe_return_time` 是预计返程时间加安全缓冲；只有它不晚于 `must_return_by` 才能通过。`spare_minutes` 是应用安全缓冲后仍剩余的时间。`reason_codes` 用于工作流稳定分支，`reasons` 用于解释；不要用自然语言文本做条件判断。

## 面向用户的最终输出

计算完成后由模型结合偏好从 `feasible` 候选中选择，工作流输出：

```json
{
  "status": "feasible",
  "message": "推荐去贵州省民族博物馆：预计16:20到达，17:30结束，18:05返回贵阳北站，另留25分钟缓冲。",
  "result_json": "{\"recommendation\":{...},\"alternatives\":[],\"rejected_candidates\":[],\"sources\":[]}" 
}
```

如果没有 `feasible` 候选，`message` 应诚实说明缺少的信息或建议不追加活动，不能从 `incomplete` 或 `infeasible` 中强选主推荐。


