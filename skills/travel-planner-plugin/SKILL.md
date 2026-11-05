---
name: travel-planner-plugin
description: 端到端旅游规划工作流编排器。TRIGGER when: 旅游规划、自由行攻略、逐日完整线路、行程报告、经费预算、景点美食、拍照点、雨天备选、途中改行程、临时空档玩什么。按顺序编排需求确认→资料核实→住宿→拍照→合成报告→复核→手册，每步前置本地 RAG 检索规范。不用于订票、付款、改签。
language: zh
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, CodeSemanticSearch
---

> 首次使用前运行 `python scripts/check_install.py <安装目录>` 自检；报告不一致时先同步 9 个 skill 目录，否则问卷、拍照等能力可能静默缺失。

# 旅行规划插件（编排器）

## 共享接口与偏好入口

先读取[共享接口](../../../docs/shared-interface.md)；平铺加载时从宿主 `TRAVEL_SHARED_ROOT/docs/shared-interface.md` 读取。在需求分析前由可信宿主调用共享工具 `prepare`，取得本次 context 和偏好快照，向用户说明沿用偏好，再分发给下游。需求分析确认新条件后丢弃旧快照，用原始本次偏好重新 prepare。当前轮各模块复用同一快照。独立拍照、住宿、重排和空档请求同样走此入口。

长期偏好保存由需求分析提供确认依据、可信宿主提交 `update`。本次日期、预算、人数和临时变化只更新本次需求。统一响应顶层 `ok` 只表示工具运行成功，行程通过与否读取 `data.result` 原始业务状态；完整安装及云端工具接入见共享接口。

本 skill 是插件主入口，不直接实现业务，只负责按序调度子 skill 并在每步前置 RAG 检索。完整调用顺序与跳过条件见 `references/orchestration.md`。

## 调用顺序

1. **RAG 检索** `python rag/retrieve.py "需求分析规范 逐轮确认 日期预算天数"` → 注入上下文
2. 调用 `travel-requirement-analysis`：逐轮确认目的地/日期/预算/天数/人数/偏好，输出需求 JSON
3. **RAG 检索** `"资料核实 天气 交通 12306 景点开放"` → 调用 `multi-platform-travel-planner`（发现+核实+天气+交通）；铁路日期、起终点已知时，本轮主动查询往返车次，不能等用户提醒。**优先用运行时 `12306-mcp`**（`get-current-date` → `get-station-code-by-names`/`get-station-code-of-citys` → `get-tickets`），用 `scripts/normalize_railway_mcp.py` 结构化并写入会话上下文 `railway_legs`；无该 MCP 时降级官方 12306 网页，都不可用则记录 `tool_unavailable`。用户未给可出发时段时先查全天候选，再确认时段后选车；`lookup_status` 非 `verified` 时不填精确车次或时刻。规程见 `skills/multi-platform-travel-planner/references/railway-mcp-workflow.md`
4. 有过夜 → **RAG** `"住宿比价 位置 房型 取消政策"` → `travel-accommodation-advisor`；当日游跳过
5. 有拍照 → **RAG** `"拍照指导 机位 姿势 构图"` → `x-xiake`；不需要拍照时跳过
6. 调用 `multi-platform-travel-planner` 合成逐日时间线+预算报告，运行 `scripts/validate_route_timeline.py`
7. **RAG** `"复核规则 时间冲突 开放预约 预算"` → `travel-plan-review`；交付前使用宿主当前时间检查 `planned` 活动，若开始时间已过，先确认实际进度或最早可出发时间并重排，fail 退回对应环节修正再复核，不能标为可执行
8. 需手册 → `travel-handbook-builder`；不需要交互手册时跳过

## 交付后分流

- 行程受扰动（晚出发/天气/闭园/预算变化）→ `travel-replanner` → `travel-plan-review` 复核 → 已有手册则 `travel-handbook-builder` 重建
- 临时空档且原行程无冲突 → `travel-time-pocket`；原行程已冲突则先 `travel-replanner`
- 现场拍照/选片 → 直接 `x-xiake`，复用既有景点与人数，不重问整个旅行预算

## 内部私有数据库

插件内置三个私有 SQLite 模块（不公开、不暴露，只服务于插件内 skill）。首次使用前运行 `python -m travel_shared.seed_knowledge` 初始化。

**模块 A — 旅行常识库**：skill 执行前先查询领域常识，避免空跑。
- `knowledge_query` action：按 category+key 精确查询，或按 keyword 模糊检索
- 分类：city_info、intercity_transport、budget_reference、accommodation_type、local_food、photo_spot、season_tip、transit_tip

**模块 B — 会话上下文存储**：需求分析确认的参数和各 skill 产出的中间结果按 trip_id 关联，下游 skill 直接读取而不重问。
- `session_put` / `session_get` / `session_get_requirements` action

**模块 C — skill 能力注册表**：比标题更详细的能力描述、触发关键词、依赖关系。编排器用它决定调用哪些 skill，比 RAG 标题匹配更精准。
- `registry_query` action：按用户查询匹配相关 skill
- `registry_list` action：列出全部 9 个 skill 的完整能力描述

**模块 D — 引导问卷**：12 步主动引导问卷，确保用户细化需求并覆盖全部 9 个 skill。用户泛泛提问时，编排器从问卷库逐步读取问题向用户提问，而不是等用户精确提问。
- `questionnaire_get_step` action：按步骤号获取引导问题（含选项、提示、触发 skill）
- `questionnaire_list` action：列出全部 12 步引导问题
- `questionnaire_next` action：获取当前步骤之后的下一个问题
- `questionnaire_dimensions` action：列出全部问卷维度

引导问卷 12 步覆盖维度：目的地→出发地→出行时间天数→人数同行者→预算→旅行风格→交通偏好→住宿偏好→拍照需求→行程复核→离线手册→应变预案。每步标注 `triggers_skill`，确保所有 9 个 skill 都有被触发的机会。可选步骤（拍照、复核、手册、应变）允许用户跳过。

调用方式：通过共享工具 `TravelTools.handle(request, user_id=...)` 发送 action 请求。

## RAG 软前置规则

- 检索成功：把 top-k chunk 注入当前子 skill 上下文作为规范提示
- 检索失败（索引未建/模型缺失/查询异常）：降级直接读子 skill 的 references 原文，不阻断流程，记录降级原因
- RAG 索引未建时提示用户运行 `python rag/build_index.py`

## 地点歧义阻断

出发地、返回地或关键接驳点对应多个实际地点（校区、院区、分店、同名景点、车站或入口）且未由用户确认时，编排必须：

1. 在 `travel-requirement-analysis` 阶段把该地点 `location_resolution.status` 标为 `ambiguous`，`poi_id` 保持 `null`，受影响的接驳时间、费用和精确出发时间标 `unknown`。可继续查询不依赖具体地点的城市级信息。
2. 由 `multi-platform-travel-planner` 搜索并列出简短候选（名称+地址），只问用户一个确认问题；搜索结果排第一、带 POI ID、被称为主校区，都不等于用户确认。
3. 用户未确认前，`location_resolution.confirmed_by_user=false`；走"询问具体地点"分支并等待回答，**禁止进入从该地点出发的路线计算、精确出门时间计算和最终行程输出分支**；禁止把行程标记为 `ready`/`pass`，禁止写入基于该地点的精确接驳时间、费用或赶车时刻。
4. 用户明确选择后，才保存地点全称、地址、POI ID 和 `confirmation_source`，置 `confirmed_by_user=true`，更新 `place_registry` 为 `confirmed`，只重查受影响路线；后续对话复用已确认地点，**不得沿用旧会话中未经用户确认的历史地点（如上次默认的某个校区/院区/分店）**，除非用户明确修改。

校验脚本（`validate_requirements.py`、`validate_route_timeline.py`）会强制上述规则：无 POI ID 或 `confirmation_source` 的 `confirmed` 无效；`ambiguous` 地点带精确时间或整体 `pass` 时 fail。

## 状态与证据交接

保留需求状态：用户明确说的值、可推导的值、仍未知的值分别标记。每个易变事实记录来源、查询时间和适用日期。下游只把已核实价格当报价；估算与采购控制额单列。任何模块缺失或外部页面不可访问，保留该栏写"待核实"，不静默填空。

## 边界

不替用户猜日期/预算/天数/人数/偏好；不执行订票/付款/改签；未经授权不定位；未运行脚本不得声称校验通过；不把搜索摘要写成亲眼看到的帖子；铁路车次/票价/余票只由 12306 直接核实。
