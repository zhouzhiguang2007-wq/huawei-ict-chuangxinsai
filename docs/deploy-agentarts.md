# 部署到华为云 AgentArts

> 平台名称以你控制台实际显示为准（华为云 AgentArts / 智能体平台）。仓库不能自动部署，以下步骤需要在控制台操作。

若你的控制台显示为“智果平台”，字段名称可能与下文不同，请以实际页面为准。部署时逐项核对以下 5 个字段：

| 控制台字段 | 核对内容 |
|---|---|
| Agent 名称 | `travel-planner`，与入口定义一致 |
| 技能绑定 | 按 `plugin.json.skills` 绑定 9 个 skill |
| 工具注册 | 共享后端 `POST /v1/tools` 可调用，核对 24 个 action 的入口 |
| MCP 配置 | 按需配置 12306-mcp、高德 MCP，并检查连接状态 |
| 环境变量 | 核对 `TRAVEL_INTERNAL_DB`、`TRAVEL_SHARED_ROOT`、`TRAVEL_TOOL_TOKENS` 的实际值与后端一致 |

## 1. 前置条件

| 项 | 要求 |
|---|---|
| Python | 3.9+（后端与工具） |
| Node.js | 18+（可选，仅 12306-mcp 需要） |
| 持久化磁盘 | **必须**。SQLite 不能放临时目录 |
| 网络 | 后端需可被 AgentArts 访问（HTTPS 或内网可达） |
| 仓库 | 完整仓库，不是只复制 `skills/` |

## 2. 部署后端（共享工具）

```bash
# 在仓库根
export TRAVEL_INTERNAL_DB=/data/travel/internal.sqlite3
export TRAVEL_TOOL_TOKENS='{"replace-with-random-token":"demo-alice"}'

python -m travel_shared.seed_knowledge
python -m travel_shared.server --db /data/travel/internal.sqlite3
# 默认监听 127.0.0.1:8765，云端需放到反向代理后的 HTTPS 入口
```

- 接口：`POST /v1/tools`，认证头 `Authorization: Bearer <token>`。
- 身份由 token 决定，请求体里的 `user_id` 会被拒绝。
- OpenAPI：`contracts/tools.openapi.json`，可在平台「工具/插件」中导入。

## 3. 导入 9 个 Skill

1. 在平台「技能 / Skill」中逐个创建，名称与目录一致。
2. 每个 skill 上传其目录内容（`SKILL.md` + `references/` + `scripts/`）。
3. 或直接上传仓库压缩包，再按 `plugin.json` 的 `skills` 列表登记。

> 只上传 `SKILL.md` 会导致 references/scripts 缺失，skill 会降级或失败。

## 4. 创建 Agent

1. 新建自定义智能体，名称 `travel-planner`。
2. 系统提示词：粘贴 `agents/travel-planner.md` 正文（frontmatter 部分按平台格式填写）。
3. 技能白名单：按 `agents/travel-planner.md` 的 `permission.skill` 允许 9 个 skill。
4. 工具：
   - 绑定已部署的 HTTP 后端（共享工具 24 个 action）。
   - 绑定 MCP（见第 5 步）。
5. 环境变量：`TRAVEL_INTERNAL_DB`、`TRAVEL_SHARED_ROOT`、`TRAVEL_TOOL_TOKENS`。

## 5. 配置 MCP（可选，影响实时性）

| MCP | 配置 | 作用 |
|---|---|---|
| `12306-mcp` | `{"command":"npx","args":["-y","12306-mcp"]}`（需 Node 18+） | 车次/余票/票价 |
| 高德 MCP | 平台市场安装或自带 key | POI/路线/接驳 |

云端若不允许本机进程，需为 12306 部署 HTTP 模式并以远程 MCP 接入，或退回浏览器工具。

## 6. RAG（可选）

```bash
python -m pip install -r requirements-rag.txt
python rag/build_index.py
```

平台侧通常不执行本地 RAG，需把索引检索改为平台知识库或后端接口；不配置时 skill 会降级读 references。

## 7. 验证

```bash
python scripts/check_mcp.py        # 铁路 MCP 可用性
python scripts/e2e_smoke.py        # 代码层闭环
```

平台内按 `docs/demo-script.md` 依次发送对话，确认 9 个 skill 均被触发，并按 `docs/acceptance-manual.md` 留证。

## 8. 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| `db_not_seeded` | 后端未 seed 或路径不一致 | 确认 `TRAVEL_INTERNAL_DB` 后重跑 seed |
| 401 | token 不匹配 | 检查 `TRAVEL_TOOL_TOKENS` 与请求头 |
| 503 | 存储/工具不可用 | 检查磁盘权限与 SQLite 文件 |
| 铁路全未知 | 未配置 12306-mcp | 按第 5 步配置，或接受降级 |
| skill 只触发 1 个 | 只导入了部分 skill | 按 `plugin.json.skills` 逐个登记 |
