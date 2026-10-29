# 数据与交付规范

脚本接收 UTF-8 JSON 对象。上游已有事实先在原 Skill 中核实，再写入这里；本模块不负责补查实时价格、车次和开放状态。

## 最小输入

```json
{
  "title": "示例旅行手册",
  "destination": "示例城市",
  "review_status": "draft",
  "review_note": "路线与价格待复核",
  "days": [
    {
      "date": "2026-11-01",
      "title": "老城步行日",
      "notes": "雨天改室内活动，现场确认开放时间",
      "stops": [
        {
          "id": "day1-museum",
          "time": "09:00",
          "name": "示例博物馆",
          "kind": "景点",
          "description": "预计参观约两小时；开放时间待核实",
          "source_url": "https://example.org/museum"
        }
      ]
    }
  ],
  "foods": [],
  "places": []
}
```

## 可选字段

- 顶层：`date_range`、`summary`、`budget_note`、`weather_note`、`open_questions`（字符串数组）、`foods`、`places`。
- 每日：`notes`、`stops`。每日 `stops` 按数组顺序呈现；时间是 `HH:MM`，可以留空，不能编造。
- 每站：`id`（跨全程唯一）、`name`、`kind`、`time`、`description`、`transport_note`、`booking_note`、`source_url`、`latitude`、`longitude`、`coordinate_system`、`coordinate_kind`、`coordinate_source_url`。有经纬度时，三项坐标说明都必填；例如坐标系是 `GCJ-02`，点位性质是“景区入口”。
- 美食项：`name`、`area`、`description`、`price_note`、`source_url`、`status`。候选餐厅不会自动加入每日行程或位置示意。
- 景点卡：`id`、`name`、`description`、`source_url`、`photo`。未提供 `places` 时，从每日站点去重生成简卡。
- `photo`：`path`、`reuse_allowed`（布尔）、`credit`、`source_url`、`note`。只有 `reuse_allowed: true` 且图片位于 JSON 文件所在目录下时，脚本才会复制图片；否则只显示文字与来源链接。公开分享前仍需由使用者确认该许可适用范围。

来源 URL 只接收 `https://`。页面对文字做转义，避免输入内容变成 HTML 脚本。输入和输出目录不要放访问令牌、证件号码或未获同意公开的订单内容。

## 交付

| 文件 | 内容 |
|---|---|
| `index.html` | 行程概览、复核状态、未决问题与三页入口 |
| `route.html` | 按日时间线和可筛选的位置示意；线段仅显示地点顺序 |
| `food.html` | 按资料显示美食/店家卡、价格口径与来源 |
| `places.html` | 景点卡与可分享的图片、来源、拍照提示 |

四页均可独立打开，不依赖第三方地图密钥。没有可信坐标时，路线页仍展示完整行程，并说明位置示意不可用。数据变更后用 `--force` 重建页面，复核入口与每页内容一致。
