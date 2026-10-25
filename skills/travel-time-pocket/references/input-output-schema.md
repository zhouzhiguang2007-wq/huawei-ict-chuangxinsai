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
  "schema_version": "1.0",
  "current_time": "2026-11-01T16:00:00+08:00",
  "must_return_by": "2026-11-01T19:00:00+08:00",
  "origin": "甲秀楼",
  "return_to": "贵阳北站",
  "buffer_minutes": 25,
  "candidates": [
    {
      "id": "c1",
      "name": "贵州省民族博物馆",
      "travel_to_minutes": 20,
      "queue_minutes": 10,
      "minimum_visit_minutes": 60,
      "travel_back_minutes": 35,
      "available": true,
      "always_open": false,
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

- `buffer_minutes`、路线、排队和游玩分钟数必须为非负整数；`minimum_visit_minutes` 应大于0。
- `available=true` 表示已确认当前可用，`false` 表示明确不可用，`null` 表示未知。
- 全天无需营业时间约束的地点设置 `always_open=true`；否则提供至少一个 `opening_windows`。
- 开放窗口的 `end` 是最晚完成活动时间，不等同于最晚入场时间。若存在停止入场时间，应在生成候选时收紧窗口。
- `evidence` 记录来源，不由计算脚本判断来源真实性。
- 候选的天气、体力、兴趣和预算筛选应在进入脚本前完成，或作为上游警告保留；代码只负责确定性时间约束。

## 计算报告

```json
{
  "status": "feasible",
  "window_minutes": 180,
  "buffer_minutes": 25,
  "candidates": [
    {
      "id": "c1",
      "name": "贵州省民族博物馆",
      "status": "feasible",
      "arrival_time": "2026-11-01T16:20:00+08:00",
      "activity_start_time": "2026-11-01T16:30:00+08:00",
      "activity_end_time": "2026-11-01T17:30:00+08:00",
      "return_time": "2026-11-01T18:05:00+08:00",
      "safe_return_time": "2026-11-01T18:30:00+08:00",
      "spare_minutes": 30,
      "reasons": []
    }
  ],
  "errors": []
}
```

`safe_return_time` 是预计返程时间加安全缓冲；只有它不晚于 `must_return_by` 才能通过。`spare_minutes` 是应用安全缓冲后仍剩余的时间。

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


