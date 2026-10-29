# 旅游规划 Skills 目录（共 9 个独立 Skill）

本目录下**每一个子文件夹都是一个独立、可单独加载的 Skill**，都有各自的 `SKILL.md`、`references/`、`scripts/`。
不是只有一个主入口——`travel-planner-plugin` 只是把它们串成完整工作流的编排器。

## Skill 清单（9 个）

| # | Skill 名 | 目录 | 作用 | 触发示例 |
|---|---|---|---|---|
| 1 | `travel-planner-plugin` | `travel-planner-plugin/` | **编排器（主入口）**：按序调度下面 7 个能力，每步前置本地 RAG | 旅游规划、自由行攻略、逐日完整线路、做一份旅游报告 |
| 2 | `travel-requirement-analysis` | `travel-requirement-analysis/` | 需求确认：逐轮问清目的地/日期/预算/天数/人数/偏好 | 帮我规划旅行、先问我缺的信息 |
| 3 | `multi-platform-travel-planner` | `multi-platform-travel-planner/` | 资料核实+报告合成：对比抖音/小红书/地图/官方源，核实景点美食天气交通，生成逐段时间线与预算 | 查景点美食天气交通、把这些并成报告 |
| 4 | `travel-accommodation-advisor` | `travel-accommodation-advisor/` | 住宿比价：位置/房型/多平台报价 | 住哪里、酒店比价、要 15 间双床房 |
| 5 | `x-xiake` | `x-xiake/` | **拍照出片教练**：机位焦段、姿势方案、拍摄口令、选片调色 | 在XX怎么拍出片、他不会拍教教他、社恐不想找路人怎么拍、这张拍得行不行帮我选选、逆光背景有垃圾桶怎么弄 |
| 6 | `travel-plan-review` | `travel-plan-review/` | 行程复核：时间冲突/开放预约/路线/预算/来源 | 检查行程、有没有时间冲突、复核一下 |
| 7 | `travel-handbook-builder` | `travel-handbook-builder/` | 离线手机手册生成 | 做成手机打开的手册、离线版 |
| 8 | `travel-replanner` | `travel-replanner/` | 途中受扰动时重排剩余行程 | 晚点了、下雨了、景点关门了、预算变了改行程 |
| 9 | `travel-time-pocket` | `travel-time-pocket/` | 临时空档微行程推荐 | 还有两小时玩什么、临时空档 |

> 注意：`x-xiake` 是**拍照 Skill**，独立可加载。若只看到 `multi-platform-travel-planner`，说明只加载了其中一个，本目录实际有 9 个 Skill。

## 完整工作流的调用顺序

由 `travel-planner-plugin` 编排（也可手动按序调用）：

1. `travel-requirement-analysis`：逐轮确认目的地、日期、预算、天数、人数和偏好。
2. `multi-platform-travel-planner`：搜索平台线索并核实景点、美食、天气与交通，按已确认日期和时间边界推算线路。
3. `travel-accommodation-advisor`：有过夜安排时比较住宿位置、房型与成本。
4. `x-xiake`：有拍照需求时，核对真实地标照片，制作带人物、构图框和机位的指导图。
5. `multi-platform-travel-planner`：为每一天生成从起点到终点的逐段时间线，运行完整线路检查，把拍照图、天气与费用并入报告。
6. `travel-plan-review`：复核时间、开放预约、路线、预算与来源后交付。
7. `travel-handbook-builder`：需要手机手册时，做成离线可打开的页面。

交付后：行程受扰动用 `travel-replanner`；临时空档且无冲突用 `travel-time-pocket`；现场拍照/选片直接用 `x-xiake`。详细条件见 `travel-planner-plugin/references/orchestration.md`。

## 加载到华为云码道（关键）

码道要求每个 Skill **平铺**在缓存目录下，不能把整个仓库文件夹塞进去：

```
C:\Users\<你>\.codeartsdoer\cache\user\skills\
├── travel-planner-plugin\        ← 拷这一个目录
├── travel-requirement-analysis\
├── multi-platform-travel-planner\
├── travel-accommodation-advisor\
├── x-xiake\                      ← 拍照 Skill，别漏
├── travel-plan-review\
├── travel-handbook-builder\
├── travel-replanner\
└── travel-time-pocket\
```

即把本目录下的 9 个文件夹**逐个**拷到 `cache\user\skills\` 下，使 `cache\user\skills\x-xiake\SKILL.md` 直接可达（不要再套一层仓库名）。
agent 定义 `agents/travel-planner.md` 拷到 `cache\user\agents\`。

加载后码道 `listSkills` 应看到 9 个 skill，其中包含 `x-xiake`。若仍只有 `multi-platform-travel-planner`，请检查是否把仓库整个文件夹当成了一个 skill、或多平台被当成了唯一主入口。

## 下载

**Code → Download ZIP**，解压后保留各文件夹内 `SKILL.md`、`references/`、`scripts/` 的相对位置。

参考提问：**"从洛阳去开封，帮我做一份包含天气、吃住行、拍照点和预算的旅游报告。请逐项问我缺少的日期、天数和预算，不要替我猜；每天按时间排出完整线路，写清每处玩多久和具体看什么。"**

这些文件是规划工作流，不会替用户购买车票、预订酒店或承诺实时价格。公开平台、地图和 12306 页面可能要求登录或限制访问；无法核实的内容须在报告里标为待核实。