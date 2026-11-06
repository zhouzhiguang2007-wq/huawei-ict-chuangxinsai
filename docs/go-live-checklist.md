# 从零到可演示：单页检查表

在完整仓库根目录执行命令；平台步骤以控制台真实界面为准。详细操作见 [环境启动](quickstart.md)、[AgentArts 部署](deploy-agentarts.md) 和 [人工验收](acceptance-manual.md)。

- [ ] **1. 取得完整代码。** `git clone https://github.com/zhouzhiguang2007-wq/huawei-ict-chuangxinsai.git`，进入仓库；观察 `plugin.json`、`skills/`、`travel_shared/`、`agents/` 均存在。
- [ ] **2. 核对运行环境。** `python --version` 应为 3.9+；若要接 12306-mcp，再核对 `node --version` 为 18+。
- [ ] **3. 固定内部库路径。** 在部署环境设置 `TRAVEL_INTERNAL_DB` 为持久化磁盘上的 `internal.sqlite3`；观察 seed 与后端使用同一值，不使用临时盘。
- [ ] **4. 初始化数据。** `python -m travel_shared.seed_knowledge`；观察输出包含 `guided_questions`，随后用 `python -m travel_shared --user-id demo-alice examples/shared-tools/questionnaire_get_step.json` 读取第 1 步。
- [ ] **5. 迁移旧偏好（仅旧库有数据时）。** 先运行 `python scripts/migrate_preferences.py --dry-run`；若 `source_rows>0`，再运行 `python scripts/migrate_preferences.py`，核对 `inserted/updated/skipped` 和 `backup`。
- [ ] **6. 核对本机宿主安装（使用 Workbuddy/码道时）。** 依 `plugin.json.skills` 复制 9 个完整目录（含 `references/` 与 `scripts/`）；`python scripts/check_install.py` 应输出“全部一致”，也可显式传本机安装目录。AgentArts 控制台上传另按第 10 步验证。
- [ ] **7. 跑代码基线。** `python scripts/run_checks.py` 退出码应为 0；`python scripts/e2e_smoke.py` 应输出“全部通过”。这一步只验证代码，不代替平台实测。
- [ ] **8. 检查可选实时工具。** 配置 12306-mcp 后运行 `python scripts/check_mcp.py`，观察握手和工具列表；天气见 [天气配置](weather-setup.md)，高德见 [住宿工具边界](accommodation-tools.md) 与 [平台部署](deploy-agentarts.md)，未配置时应明确降级。
- [ ] **9. 启动共享后端。** 设置受保护的 `TRAVEL_TOOL_TOKENS`，运行 `python -m travel_shared.server`；观察 `POST /v1/tools` 正确 token 可调用、错误 token 返回 401，并通过可达 HTTPS 接入平台。
- [ ] **10. 完成平台绑定。** 在 AgentArts（或控制台实际名称）创建 `travel-planner`，导入 9 个 skill，绑定共享工具与可选 MCP；观察 Agent 名称、技能绑定、工具注册、MCP 配置、环境变量这 5 项与 [部署说明](deploy-agentarts.md) 一致。
- [ ] **11. 走真实问答。** 按 [演示脚本](demo-script.md) 发起旅行需求，观察 Agent 逐轮完成 13 步问卷，并实际调用需求、规划、住宿、拍照、复核、手册能力；记录工具名、入参、返回和耗时。
- [ ] **12. 验证旅途中变化。** 发送“高铁晚点了”和“还有两小时去哪”，观察重排不改已发生段、空档方案保留安全缓冲；按 [人工验收](acceptance-manual.md) 检查跨用户隔离与重启后的会话读取。
- [ ] **13. 留存比赛证据。** 保存平台调用截图或录屏、时间线行程、复核结果与离线手册；静态 Demo 只标为示例，实时车次、天气和住宿价格以实际工具返回及查询时间为准。

未通过的平台步骤不得仅凭 `e2e_smoke` 结果标为“已上线”；缺少 MCP 或外部数据时记录降级状态。
