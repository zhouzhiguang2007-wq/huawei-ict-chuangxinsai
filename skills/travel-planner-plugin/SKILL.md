---
name: travel-planner-plugin
description: 端到端旅游规划工作流编排器。TRIGGER when: 旅游规划、自由行攻略、逐日完整线路、行程报告、经费预算、景点美食、拍照点、雨天备选、途中改行程、临时空档玩什么。按顺序编排需求确认→资料核实→住宿→拍照→合成报告→复核→手册，每步前置本地 RAG 检索规范。不用于订票、付款、改签。
language: zh
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, CodeSemanticSearch
---

# 旅行规划插件（编排器）

本 skill 是插件主入口，不直接实现业务，只负责按序调度子 skill 并在每步前置 RAG 检索。完整调用顺序与跳过条件见 `references/orchestration.md`。

## 调用顺序

1. **RAG 检索** `python rag/retrieve.py "需求分析规范 逐轮确认 日期预算天数"` → 注入上下文
2. 调用 `travel-requirement-analysis`：逐轮确认目的地/日期/预算/天数/人数/偏好，输出需求 JSON
3. **RAG 检索** `"资料核实 天气 交通 12306 景点开放"` → 调用 `multi-platform-travel-planner`（发现+核实+天气+交通）
4. 有过夜 → **RAG** `"住宿比价 位置 房型 取消政策"` → `travel-accommodation-advisor`；当日游跳过
5. 有拍照 → **RAG** `"拍照指导 机位 姿势 构图"` → `x-xiake`；不需要拍照时跳过
6. 调用 `multi-platform-travel-planner` 合成逐日时间线+预算报告，运行 `scripts/validate_route_timeline.py`
7. **RAG** `"复核规则 时间冲突 开放预约 预算"` → `travel-plan-review`；交付前使用宿主当前时间检查 `planned` 活动，若开始时间已过，先确认实际进度或最早可出发时间并重排，fail 退回对应环节修正再复核，不能标为可执行
8. 需手册 → `travel-handbook-builder`；不需要交互手册时跳过

## 交付后分流

- 行程受扰动（晚出发/天气/闭园/预算变化）→ `travel-replanner` → `travel-plan-review` 复核 → 已有手册则 `travel-handbook-builder` 重建
- 临时空档且原行程无冲突 → `travel-time-pocket`；原行程已冲突则先 `travel-replanner`
- 现场拍照/选片 → 直接 `x-xiake`，复用既有景点与人数，不重问整个旅行预算

## RAG 软前置规则

- 检索成功：把 top-k chunk 注入当前子 skill 上下文作为规范提示
- 检索失败（索引未建/模型缺失/查询异常）：降级直接读子 skill 的 references 原文，不阻断流程，记录降级原因
- RAG 索引未建时提示用户运行 `python rag/build_index.py`

## 状态与证据交接

保留需求状态：用户明确说的值、可推导的值、仍未知的值分别标记。每个易变事实记录来源、查询时间和适用日期。下游只把已核实价格当报价；估算与采购控制额单列。任何模块缺失或外部页面不可访问，保留该栏写"待核实"，不静默填空。

## 边界

不替用户猜日期/预算/天数/人数/偏好；不执行订票/付款/改签；未经授权不定位；未运行脚本不得声称校验通过；不把搜索摘要写成亲眼看到的帖子；铁路车次/票价/余票只由 12306 直接核实。
