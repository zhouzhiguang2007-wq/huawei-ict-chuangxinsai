# huawei-ict-chuangxinsai

华为 ICT 旅游规划 Agent Skills。

## 共享接口与 SQLite 用户偏好

项目新增统一交接 `context` 和标准库工具 `travel_shared`：SQLite 保存用户确认的长期偏好，需求分析负责理解，主编排统一分发同一份偏好快照。九个 Skill 均接入共享规范，现有业务脚本接口保留。

先看[安装、接口与 AgentArts 接入说明](docs/shared-interface.md)，再按[模拟请求](examples/shared-tools/)试跑。在完整仓库根运行 `python -m travel_shared --user-id demo-alice examples/shared-tools/get.json`；Python 3.9+，无第三方依赖。运行 `python scripts/run_checks.py` 验证共享接口与原有脚本。新增[需求分析 Agent 定义](agents/travel-requirement-analysis.md)可供码道加载或 AgentArts 提示词迁移。

平铺复制 Skill 时，还须保留完整仓库作为共享工具运行目录并配置宿主 `TRAVEL_SHARED_ROOT`。云端需注册可达后端工具并配置持久化磁盘；仓库文件不会自动部署到 AgentArts。用户偏好与现有 RAG 规范库独立，不把用户档案加入公共索引。

## 快速开始

1. 打开 [Skills 使用顺序](skills/README.md)，了解先问需求、再核实资料和交通天气、最后生成并复核报告的流程。
2. 本仓库共 9 个独立 skill，完整清单见 [Skills 清单](skills/README.md)；完整规划由 [travel-planner-plugin](skills/travel-planner-plugin/SKILL.md) 编排。
3. 点击本仓库的 **Code → Download ZIP** 下载全部文件，解压后保留各 Skill 文件夹内的相对路径。

该项目提供规划工作流和计算校验工具。实时票价、房态、天气及景区开放信息需要在每次使用时重新核实；不会自动购买或预订。

## 旅行规划插件（华为云码道适配）

本仓库已封装为华为云码道（CodeArts Agent）本地插件包：原有 7 个 skill 已做码道适配（删除 `agents/openai.yaml`、`x-xiake` frontmatter 精简），并新增主入口 [`skills/travel-planner-plugin`](skills/travel-planner-plugin/SKILL.md) 编排完整工作流，配套自建本地 RAG。

**本仓库含 9 个独立 skill**（含拍照 skill [`x-xiake`](skills/x-xiake/SKILL.md)），每个均可单独加载。完整清单与码道加载方式见 [`skills/README.md`](skills/README.md)。若码道只看到 `multi-platform-travel-planner`，说明只加载了其中一个，请按该清单平铺加载全部 9 个。

### 码道加载使用

1. 下载本仓库 ZIP（**Code → Download ZIP**），解压。
2. 把 `skills/*` 拷到 `C:\Users\<你>\.codeartsdoer\cache\user\skills\`，把 `agents/travel-planner.md` 拷到 `...cache\user\agents\`。
3. 建 RAG 索引（在仓库根运行）：
   ```bash
   pip install sentence-transformers numpy pyyaml
   python rag/build_index.py
   ```
4. 重启码道会话，对 Agent 说"从洛阳去开封，帮我做一份包含天气、吃住行、拍照点和预算的旅游报告"，即触发 `travel-planner-plugin`。

### 编排顺序

需求确认 → 资料核实 → 住宿 → 拍照 → 合成报告 → 复核 → 手册，每步前置本地 RAG 检索规范。途中受扰动用 `travel-replanner`，临时空档用 `travel-time-pocket`。

### 关键文件

- [`plugin.json`](plugin.json) 自描述元数据
- [`agents/travel-planner.md`](agents/travel-planner.md) 码道 agent 定义（permission.skill 白名单）
- [`rag/`](rag/) 本地向量库（`build_index.py` 建库 / `retrieve.py` 检索）

不替用户猜日期/预算/天数/人数/偏好；不执行订票/付款/改签；未经授权不定位。
