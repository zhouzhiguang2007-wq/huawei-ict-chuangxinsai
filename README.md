# huawei-ict-chuangxinsai

华为 ICT 旅游规划 Agent 插件（v0.3.0）。整仓即插件包：1 个编排 agent + 9 个 skill + 共享数据层 + 可选 RAG + 可选 MCP。

## 这是什么

不是 9 个分散的 skill，而是一套整体：

- **一个入口**：`agents/travel-planner.md`，触发后交给编排器。
- **一个编排器**：`skills/travel-planner-plugin`，按 13 步问卷 → 需求 → 核实 → 住宿 → 拍照 → 合成 → 复核 → 手册执行。
- **8 个执行 skill**：需求分析、资料核实、住宿、拍照、复核、手册、重排、空档。
- **一层共享状态**：`travel_shared`（SQLite：知识/会话/注册表/问卷/偏好，24 个 action）。
- **外部能力**：本地 RAG（可选）、12306-mcp（可选）、天气（彩云官方 MCP / Open-Meteo 回退）、高德 MCP（可选）、住宿（仅网页，无官方 API）。

完整关系见 [skill 关系图](docs/skill-map.md)，分层与数据流见 [整体架构](docs/architecture.md)。

## 快速开始

1. [环境与启动顺序](docs/quickstart.md)：初始化、迁移、自检、RAG、MCP。
2. [部署到 AgentArts](docs/deploy-agentarts.md)：后端、skill、agent、工具、MCP 的配置步骤。
3. [现场演示脚本](docs/demo-script.md)：覆盖 9 个 skill 的对话样例。
4. [人工验收清单](docs/acceptance-manual.md)：平台内验收与留证。
5. 代码层基线：`python scripts/e2e_smoke.py`。

```bash
python -m travel_shared.seed_knowledge     # 初始化内部库
python scripts/check_install.py ~/.workbuddy/skills
python scripts/run_checks.py                # CI 同款全量检查
python scripts/export_plugin.py             # 生成可分发包
```

## 共享接口与 SQLite

`travel_shared` 统一保存：旅行常识、会话上下文（按 `user_id` 隔离）、skill 注册表、13 步引导问卷、用户偏好。默认同库 `~/.travel-planner/internal.sqlite3`，可用 `TRAVEL_INTERNAL_DB` 指定。接口规范见 [docs/shared-interface.md](docs/shared-interface.md)，OpenAPI 见 [contracts/tools.openapi.json](contracts/tools.openapi.json)。

在完整仓库根运行 `python -m travel_shared --user-id demo-alice examples/shared-tools/get.json`；Python 3.9+，核心功能无第三方依赖。运行 `python scripts/run_checks.py` 验证共享接口与原有脚本。

平铺复制 Skill 时，还须保留完整仓库作为共享工具运行目录并配置宿主 `TRAVEL_SHARED_ROOT`。云端需注册可达后端工具并配置持久化磁盘；仓库文件不会自动部署到 AgentArts。用户偏好不加入公共 RAG 索引。

## 码道 / AgentArts 加载

1. 下载本仓库 ZIP，解压。优先用 `python scripts/export_plugin.py` 生成的分发包。
2. 把 9 个 `skills/<name>/` 平铺到宿主 skills 目录（码道：`~/.codeartsdoer/cache/user/skills/`；workbuddy：`~/.workbuddy/skills/`），把 `agents/travel-planner.md` 放到 agents 目录。
3. 建 RAG 索引（可选）：
   ```bash
   python -m pip install -r requirements-rag.txt
   python rag/build_index.py
   ```
4. 重启会话，说“帮我做一份贵阳三天两晚的自由行攻略，两个人，预算 3000 元”。

若只看到 `multi-platform-travel-planner`，说明只加载了其中一个，请按 [Skills 清单](skills/README.md) 平铺全部 9 个。

## 编排顺序

需求确认 → 资料核实 → 住宿 → 拍照 → 合成报告 → 复核 → 手册；交付后受扰动用 `travel-replanner`，临时空档用 `travel-time-pocket`。

## 关键文件

- [plugin.json](plugin.json)：插件清单（skills、关系图、部署、验收）
- [plugin.schema.json](plugin.schema.json)：清单结构约束
- [agents/travel-planner.md](agents/travel-planner.md)：码道 agent 定义（permission.skill 白名单）
- [docs/skill-map.md](docs/skill-map.md)：9 个 skill 的上下游与触发关键词
- [docs/architecture.md](docs/architecture.md)：分层、数据流、降级
- [docs/deploy-agentarts.md](docs/deploy-agentarts.md)：部署步骤
- [docs/demo-script.md](docs/demo-script.md)：演示脚本
- [docs/acceptance-manual.md](docs/acceptance-manual.md)：人工验收
- [docs/weather-setup.md](docs/weather-setup.md)：天气接入（官方 MCP + 回退）
- [docs/accommodation-tools.md](docs/accommodation-tools.md)：住宿工具现状与边界
- [rag/](rag/)：本地向量库（可选）
- [CHANGELOG.md](CHANGELOG.md)：版本变更

本项目提供规划工作流和计算校验工具。实时票价、房态、天气及景区开放信息需要在每次使用时重新核实；不会自动购买或预订。不替用户猜日期/预算/天数/人数/偏好；不执行订票/付款/改签；未经授权不定位。