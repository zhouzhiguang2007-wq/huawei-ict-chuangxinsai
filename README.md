# huawei-ict-chuangxinsai

华为 ICT 旅游规划 Agent Skills。

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
