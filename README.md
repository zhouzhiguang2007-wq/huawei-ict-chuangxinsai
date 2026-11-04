# 华为 ICT 旅游规划 Agent 插件

本仓库包含 9 个可独立加载的旅游 Skill、一个完整行程编排入口、用于检索工作规范的本地 RAG，以及用于多 Agent 共享用户已确认偏好的工具。完整清单见 [Skills 说明](skills/README.md)，统一数据与工具约定见 [共享接口](docs/shared-interface.md)。

用户要求“旅游报告”“完整行程”或攻略文件时，主入口 `travel-planner-plugin` 先确认目的地、日期、天数、人数和预算，再核实景点、交通、天气与住宿，安排逐日从起点到终点的线路，写清每段时间、游玩内容、接驳、餐饮休息和费用，复核后交付。拍照、途中重排和临时空档推荐也可独立调用。实时票价、房态、天气、开放与预约信息须在使用时重新核实；插件不代购、代订或代付款。

## 获取与本地检查

下载仓库 ZIP 或克隆仓库后，在**完整仓库根目录**运行：

```powershell
python -m pip install pytest
python scripts/run_checks.py
python rag/scripts/validate_index.py
python -m travel_shared --user-id demo-alice examples/shared-tools/get.json
```

统一检查覆盖插件清单、九个 Skill、本地脚本、共享接口、内部数据库测试及 RAG 索引新鲜度。共享工具运行只依赖 Python 3.9+ 标准库；完整测试另需 `pytest`（GitHub CI 会安装）。RAG **重建及语义检索**另需安装 `sentence-transformers`、`numpy`、`pyyaml`。`get.json` 是虚构用户的只读示例；要避免保存演示数据，可给 CLI 添加 `--db` 指向临时数据库。

若修改了 `skills/**/SKILL.md`、Skill 的 `references/*.md`、`docs/*.md` 或 `rag/config.yaml`，索引会被标为过期。在编辑完成后运行：

```powershell
python -m pip install sentence-transformers numpy pyyaml
python rag/build_index.py
python rag/scripts/validate_index.py
python rag/retrieve.py "开封两天完整线路"
```

构建优先复用本地模型缓存，缺少模型时会下载；`python rag/build_index.py --offline` 要求模型已缓存。检索默认只使用本地模型，缺缓存时会说明原因，不会反复联网。索引文件位于 `rag/index/`，应与本次改动一起提交。索引只收录 Skill 与公共工作流说明，不收录个人偏好数据库。

## 两套 SQLite 数据

长期偏好默认保存在 `~/.travel-planner/preferences.sqlite3`，可用 `TRAVEL_PREFERENCES_DB` 更改。新增的旅行常识、行程会话和 Skill 能力注册表保存在另一文件 `~/.travel-planner/internal.sqlite3`，可用 `TRAVEL_INTERNAL_DB` 更改；首次使用前运行 `python -m travel_shared.seed_knowledge` 建表并写入预置常识。两个路径都应指向宿主的持久化磁盘。

预置常识提供规划起点，票价、天气、开放时间和班次仍须实时核实。内部常识、会话及注册表操作只供持有可信身份的 Python 宿主调用；公开 HTTP 与 AgentArts 桥接仅接受 `plugin.json` 中列出的六个共享操作。行程会话按可信用户身份隔离，升级前没有归属信息的旧会话行保留但不会自动认领，见[部署与联调说明](docs/deployment-readiness.md)。

## 在华为云码道本地加载

1. 保留一份**完整仓库**，它提供 `rag/`、`travel_shared/`、`docs/` 和业务脚本。
2. 按 [Skills 说明](skills/README.md) 将 `skills/` 下的 9 个文件夹逐个平铺复制到 `C:\Users\<你>\.codeartsdoer\cache\user\skills\`；将 `agents/travel-planner.md` 复制到同级 `agents\`。
3. 在可信宿主配置 `TRAVEL_SHARED_ROOT` 为完整仓库根目录，按 [部署与联调说明](docs/deployment-readiness.md)配置共享工具入口、持久化数据库和偏好快照密钥。平铺后的 Skill 目录本身没有 `rag/` 或 `travel_shared/`。
4. 重启码道会话，确认 `listSkills` 能看到全部 9 个 Skill，再请求一份带逐日时间线的旅游报告。

仅平铺复制 Skill 时，普通规划说明仍可使用；历史偏好读取、保存和 RAG 检索需宿主实际接通相应工具。Agent 文件中的 `mcp_tools: {}` 不会自动注册这些工具。

## AgentArts 接入范围

GitHub 中的源码、索引与本地测试不等于 AgentArts 云端部署。云端还需在目标项目中部署可达的 HTTPS 工具后端、配置鉴权与持久化存储，并将工具注册到工作流；本地 CodeArts 缓存路径不能被云端节点直接访问。工具协议及读写权限见 [共享接口](docs/shared-interface.md)，逐项本地联调和平台接入步骤见 [部署与联调说明](docs/deployment-readiness.md)。

长期偏好只在用户明确确认后由可信后端写入。身份、写入凭据及 `TRAVEL_SNAPSHOT_SECRET` 不应放入提示词、前端或仓库。业务脚本返回的 `fail` 或 `incomplete` 不可当作可执行行程交付。
