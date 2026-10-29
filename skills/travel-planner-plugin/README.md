# travel-planner-plugin · 华为云码道旅行规划插件

端到端旅游规划工作流：需求确认 → 资料核实 → 住宿 → 拍照 → 合成报告 → 复核 → 手册，含自建本地 RAG。

源自 GPT `team-travel-skills-2026-10-25/skills`（7 个 skill），封装为华为云码道（CodeArts Agent）本地插件包。

## 目录结构

```
travel-planner-plugin/
├── plugin.json          自描述元数据（码道不强制读）
├── skills/              1 主入口 + 7 子 skill（码道加载此处）
├── agents/travel-planner.md   码道 agent 定义（permission.skill 白名单）
└── rag/                 本地向量库（build_index.py / retrieve.py / index/）
```

## 安装

### 1. 放到码道 cache（user scope，推荐）

```bash
# skills
cp -r travel-planner-plugin/skills/* "C:/Users/Lenovo/.codeartsdoer/cache/user/skills/"
# agent 定义
cp travel-planner-plugin/agents/travel-planner.md "C:/Users/Lenovo/.codeartsdoer/cache/user/agents/"
```

若 user scope 需状态文件（待核实），按 system 的 `SystemSkillStatus.txt` 格式追加：

```
travel-planner-plugin=true
travel-requirement-analysis=true
multi-platform-travel-planner=true
travel-accommodation-advisor=true
x-xiake=true
travel-plan-review=true
travel-handbook-builder=true
travel-replanner=true
travel-time-pocket=true
```

重启码道会话，`listSkills` 应见 `travel-planner-plugin`。

### 2. 建 RAG 索引

```bash
cd travel-planner-plugin
pip install sentence-transformers numpy pyyaml
python rag/build_index.py
python rag/retrieve.py "天气核实规范"   # 自检，应返回 top-k chunks
```

首次运行自动下载 embedding 模型（约 120MB）。

## 使用

对码道 Agent 说：

> 从洛阳去开封，帮我做一份包含天气、吃住行、拍照点和预算的旅游报告。请逐项问我缺少的日期、天数和预算，不要替我猜；每天按时间排出完整线路，写清每处玩多久和具体看什么。

Agent 会调用 `travel-planner-plugin`，按编排顺序逐项确认需求、核实资料、生成报告并复核。

## 设计文档

- `docs/design/PRD-旅行规划插件.md`
- `docs/design/HLD-旅行规划插件.md`

## 边界

不替用户猜日期/预算/天数/人数/偏好；不执行订票/付款/改签；未经授权不定位；未运行脚本不得声称校验通过。