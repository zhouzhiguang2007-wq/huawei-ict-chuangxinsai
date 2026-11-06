# 插件 skill 关系图

> 本文件由 `scripts/render_skill_map.py` 从 `plugin.json` 与 `travel_shared.seed_knowledge.SKILL_REGISTRY_DATA` 生成，请勿手工修改。

## 全景

```
travel-planner-agent
        |
        v
travel-planner-plugin  (编排器)
        |
        +--> travel-requirement-analysis   需求确认 / 引导问卷
        +--> multi-platform-travel-planner 资料核实 / 铁路 / 逐日时间线
        +--> travel-accommodation-advisor  住宿比价
        +--> x-xiake                       拍照出片指导
        +--> travel-plan-review            行程复核
        +--> travel-handbook-builder       离线手册
        +--> travel-replanner              途中重排
        +--> travel-time-pocket            临时空档微行程
```

所有 skill 通过同一份共享状态协作：`travel_shared`（SQLite 内部私有库 + 24 个 action）。

## skill 清单

| Skill | 类别 | 上游 | 下游 | 触发关键词 | 产出 |
|---|---|---|---|---|---|
| `travel-planner-plugin` | orchestrator | — | multi-platform-travel-planner、travel-accommodation-advisor、travel-handbook-builder、travel-plan-review、travel-replanner、travel-requirement-analysis、travel-time-pocket、x-xiake | 旅游规划、自由行、攻略、行程、旅游报告、逐日线路、预算、景点、美食、拍照、雨天备选、改行程、空档 | 完整逐日行程报告（时间线+预算+景点+美食+拍照+天气+交通） |
| `travel-requirement-analysis` | analysis | travel-planner-plugin | multi-platform-travel-planner、travel-accommodation-advisor | 规划旅行、帮我旅游、想去旅游、先问我、缺的信息、目的地、出发日期、预算、天数、人数、偏好 | 结构化需求JSON（destination/dates/budget/travelers/preferences） |
| `multi-platform-travel-planner` | planning | travel-planner-plugin、travel-requirement-analysis、x-xiake | travel-accommodation-advisor、travel-plan-review、x-xiake | 查景点、查美食、查天气、查交通、12306、高铁、火车、机票、合成报告、逐日时间线、路线 | 候选景点+证据表+天气窗口+交通表+逐日时间线+预算报告 |
| `travel-accommodation-advisor` | accommodation | multi-platform-travel-planner、travel-planner-plugin、travel-requirement-analysis | — | 住哪里、酒店、住宿、比价、民宿、双床房、大床房、15间、退房、取消政策 | 候选住宿方案（位置/房型/报价/取消政策/总价） |
| `x-xiake` | photo | multi-platform-travel-planner、travel-planner-plugin | multi-platform-travel-planner | 拍照、出片、机位、姿势、构图、焦段、拍摄口令、选片、调色、社恐、路人、逆光 | 拍照指导图+机位焦段+姿势方案+拍摄口令+选片调色建议 |
| `travel-plan-review` | review | multi-platform-travel-planner、travel-planner-plugin、travel-replanner | travel-handbook-builder、travel-replanner、travel-time-pocket | 检查行程、复核、时间冲突、开放预约、路线检查、预算校验、来源核实 | 复核结果（通过/阻断问题列表+退回修正建议） |
| `travel-handbook-builder` | handbook | travel-plan-review、travel-planner-plugin | — | 手机手册、离线版、离线手册、做成页面、手机打开 | 离线HTML手册（概览+每日路线+位置示意+美食景点页面） |
| `travel-replanner` | replanner | travel-plan-review、travel-planner-plugin | travel-plan-review | 晚点了、下雨了、关门了、景点关闭、预算变了、改行程、行程变动、延误、天气变化 | 重排后的剩余行程（保留有效条件+修改受影响部分） |
| `travel-time-pocket` | pocket | travel-plan-review、travel-planner-plugin | — | 还有两小时、空档、临时、碎片时间、等车、等飞机、附近玩什么 | 微行程方案（去回程时间+游玩内容+安全缓冲） |

## 共享状态

| 状态 | 表 | 使用方式 |
|---|---|---|
| 需求与会话上下文 | `session_context` | `session_put` / `session_get`，按 `user_id` 隔离 |
| 旅行常识 | `travel_knowledge` | `knowledge_query`（城市/交通/预算/住宿/美食/机位/季节） |
| 能力注册表 | `skill_registry` | `registry_query` 按触发关键词匹配 skill |
| 引导问卷 | `guided_questions` | `questionnaire_get_step` 逐轮提问，13 步 |
| 用户偏好 | `preferences` | `get` / `update` / `delete` / `clear`，按 `user_id` 隔离 |

## 调用顺序

主流程：`travel-requirement-analysis → multi-platform-travel-planner → travel-accommodation-advisor → x-xiake → multi-platform-travel-planner → travel-plan-review → travel-handbook-builder`

交付后分流：`travel-replanner / travel-time-pocket`

## 依赖边

| 从 | 到 | 含义 |
|---|---|---|
| `travel-planner-plugin` | `travel-requirement-analysis` | delegates |
| `travel-planner-plugin` | `multi-platform-travel-planner` | delegates |
| `travel-planner-plugin` | `travel-accommodation-advisor` | delegates |
| `travel-planner-plugin` | `x-xiake` | delegates |
| `travel-planner-plugin` | `travel-plan-review` | delegates |
| `travel-planner-plugin` | `travel-handbook-builder` | delegates |
| `travel-requirement-analysis` | `multi-platform-travel-planner` | requirements |
| `travel-requirement-analysis` | `travel-accommodation-advisor` | requirements |
| `multi-platform-travel-planner` | `travel-accommodation-advisor` | spots_and_dates |
| `multi-platform-travel-planner` | `x-xiake` | spots |
| `x-xiake` | `multi-platform-travel-planner` | photo_guides |
| `multi-platform-travel-planner` | `travel-plan-review` | itinerary |
| `travel-plan-review` | `travel-handbook-builder` | reviewed_itinerary |
| `travel-plan-review` | `travel-replanner` | blocking_issue |
| `travel-replanner` | `travel-plan-review` | replanned_itinerary |
| `travel-plan-review` | `travel-time-pocket` | free_window |
| `travel-planner-plugin` | `travel-replanner` | delegates |
| `travel-planner-plugin` | `travel-time-pocket` | delegates |
