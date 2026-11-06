# 变更记录

## 0.3.0 — 2026-11-06

收尾版本：把 9 个 skill 收拢为一个整体插件，并补齐部署与验收材料。

### 新增
- 插件清单：`plugin.json` 增加 `skill_graph`（节点/依赖边/共享状态）、`deployment`、`acceptance`。
- `plugin.schema.json` 随之扩展。
- `docs/skill-map.md`：由 `scripts/render_skill_map.py` 从清单与注册表生成，避免手抄漂移。
- `docs/architecture.md`：分层、数据流、状态职责、失败降级。
- `docs/deploy-agentarts.md`：华为云 AgentArts 部署步骤与常见失败。
- `docs/demo-script.md`：覆盖 9 个 skill 的现场演示脚本。
- `docs/acceptance-manual.md`：人工验收清单。
- `scripts/export_plugin.py`：生成可分发的插件压缩包。
- 测试：`tests/test_skill_map.py`、`tests/test_export_plugin.py`。

### 变更
- 安装自检 `scripts/check_install.py` 覆盖整个 skill 目录，不再只比对 `SKILL.md`。
- README 快速开始改为指向 `docs/quickstart.md` 与部署文档。

## 0.2.0 — 2026-11-06

### 新增
- 内部私有 SQLite 库：知识库、会话上下文、skill 注册表、引导问卷（13 步）、用户偏好同库。
- 会话上下文按 `user_id` 隔离，旧表首次连接自动迁移。
- `scripts/migrate_preferences.py`：旧偏好迁移（dry-run/备份/保留较新）。
- `scripts/check_mcp.py`：12306-mcp 握手与工具自检。
- `scripts/e2e_smoke.py`：代码层 10 步闭环。
- 12306-mcp 接入规程写进 `multi-platform-travel-planner` 等 skill。
- `requirements-rag.txt` 与 `docs/quickstart.md`。

### 变更
- 安装自检与 shared_tools 声明补全（actions 6 → 24；contract_version 1.1）。
- 数据库路径统一：seed 与运行时共用 `TRAVEL_INTERNAL_DB`。

## 0.1.0 — 2026-10

### 新增
- 9 个 skill 的码道适配与主入口编排器。
- 本地 RAG 向量库（243 → 259 chunks）。
- 共享上下文与偏好快照（`travel_shared`）。