# 插件整体架构

本插件不是 9 个孤立 skill，而是一套「一个 Agent + 一个编排器 + 8 个执行 skill + 一层共享状态」的整体。

## 1. 分层

```
┌─────────────────────────────────────────────────────────────┐
│ 宿主：华为云 AgentArts / 华为云码道                            │
│  - 提供模型、文件工具、MCP、HTTP 工具、持久化磁盘              │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│ Agent：agents/travel-planner.md                              │
│  - 触发识别、skill 白名单、工具权限、失败降级                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│ 编排器：travel-planner-plugin                                │
│  - 13 步问卷 → 需求确认 → 资料核实 → 住宿 → 拍照 →          │
│    合成报告 → 复核 → 手册；交付后重排 / 空档分流              │
└───────┬──────────┬──────────┬──────────┬──────────┬─────────┘
        │          │          │          │          │
   requirement  multi-platform  accommodation  x-xiake  review
        │          │          │          │          │
        └──────────┴────┬─────┴──────────┴──────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│ 共享层：travel_shared（SQLite 内部私有库 + 24 个 action）      │
│  knowledge / session / registry / questionnaire / preferences│
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼────────────────┐
        │               │                │
   本地 RAG（可选）   12306-mcp（可选）   高德 MCP（可选）
```

## 2. 数据流

1. **引导**：`questionnaire_get_step` 逐轮向用户提问，13 步覆盖 8 个执行 skill。
2. **需求**：`travel-requirement-analysis` 输出需求 JSON，写入 `session_context`（`stage=confirmed`）。
3. **核实**：`multi-platform-travel-planner` 读取 `travel_knowledge`，查询铁路/天气/交通，写入 `stage=verified`。
4. **住宿**：`travel-accommodation-advisor` 读取需求和候选景点，输出候选住宿。
5. **拍照**：`x-xiake` 读取景点清单，输出机位/姿势/拍摄口令。
6. **合成**：`multi-platform-travel-planner` 汇总为逐日时间线，调用 `validate_route_timeline.py`。
7. **复核**：`travel-plan-review` 校验时间、开放、交通、预算，结果写入 `stage=review_result`。
8. **手册**：`travel-handbook-builder` 读取已复核行程，生成离线 HTML。
9. **分流**：扰动用 `travel-replanner` 重排后回到复核；空档用 `travel-time-pocket`。

## 3. 共享状态职责

| 状态 | 表 | 写入方 | 读取方 |
|---|---|---|---|
| 需求与会话上下文 | `session_context` | 需求分析、规划、住宿、拍照、复核、重排 | 所有下游 skill |
| 旅行常识 | `travel_knowledge` | seed + 人工补充 | 规划、住宿、拍照、重排、空档 |
| 能力注册表 | `skill_registry` | seed | 编排器（能力发现） |
| 引导问卷 | `guided_questions` | seed | 编排器（逐轮提问） |
| 用户偏好 | `preferences` | 宿主经用户确认后写入 | 编排器（prepare 快照） |

会话与偏好均按可信 `user_id` 隔离；`session_context` 旧表首次连接自动迁移。

## 4. 失败降级

| 能力 | 缺失时行为 |
|---|---|
| 内部库未初始化 | `prepare` 返回 `status=unavailable`、`reason=db_not_seeded`，提示运行 seed |
| 12306-mcp | 降级官方网页 → 都不可用则 `lookup_status=tool_unavailable`，铁路段标未知 |
| 高德 MCP | 用公开地图网页核实并记录来源与时间 |
| 本地 RAG | 降级直接读 skill 的 references，不阻断流程 |
| 天气/住宿 | 网页检索 + 标注来源与查询时间，不伪造数据 |

## 5. 目录结构

```
plugin.json              # 插件清单（skills、关系图、部署、验收）
plugin.schema.json       # 清单结构约束
agents/                  # 码道 Agent 定义
skills/                  # 9 个可单独加载的 skill
travel_shared/           # 共享层：SQLite + 24 action
rag/                     # 可选本地向量库
contracts/               # OpenAPI 契约
scripts/                 # 自检、迁移、打包、e2e
docs/                    # 接口、架构、部署、验收
tests/                   # 349+ 用例
```