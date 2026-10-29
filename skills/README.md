# 旅游规划 Skills：使用顺序

主入口是 [`multi-platform-travel-planner`](multi-platform-travel-planner/SKILL.md)。完整旅行报告按以下顺序进行：

1. [`travel-requirement-analysis`](travel-requirement-analysis/SKILL.md)：逐轮确认目的地、日期、预算、天数、人数和偏好。
2. `multi-platform-travel-planner`：搜索平台线索并核实景点、美食、天气与交通，按已确认日期和时间边界推算线路。
3. [`travel-accommodation-advisor`](travel-accommodation-advisor/SKILL.md)：有过夜安排时比较住宿位置、房型与成本。
4. [`x-xiake`](x-xiake/SKILL.md)：有拍照需求时，核对真实地标照片，制作带完整人物、构图框和机位说明的指导图，并交回照片来源、合成标记和现场待核实项。
5. `multi-platform-travel-planner`：为每一天生成从起点到终点的逐段时间线，标出每处游玩时长、转场、餐饮休息和具体体验；运行完整线路检查，再把拍照图、天气与费用并入报告。
6. [`travel-plan-review`](travel-plan-review/SKILL.md)：复核时间、开放预约、路线、预算与来源后交付。
7. [`travel-handbook-builder`](travel-handbook-builder/SKILL.md)：需要手机端手册时，把复核后的行程做成离线可打开的概览、每日路线、美食与景点页面。

交付后，行程受扰动用 [`travel-replanner`](travel-replanner/SKILL.md) 调整，复核后重新生成手册；临时空档且原行程不冲突时用 [`travel-time-pocket`](travel-time-pocket/SKILL.md) 推荐可按时返回的小活动。详细的输入、输出和跳过条件见[调用顺序说明](multi-platform-travel-planner/references/workflow-orchestration.md)。

## 下载与使用

在仓库页面选择 **Code → Download ZIP**，解压后打开 `skills/`。可把需要的整个 Skill 文件夹安装到支持 Skill 的助手中；请保留各文件夹的 `SKILL.md`、`references/` 和 `scripts/` 的相对位置。也可先打开主入口文件，按其中引用读取专项说明。

参考提问：**“从洛阳去开封，帮我做一份包含天气、吃住行、拍照点和预算的旅游报告。请逐项问我缺少的日期、天数和预算，不要替我猜；每天按时间排出完整线路，写清每处玩多久和具体看什么。”**

这些文件是规划工作流，不会替用户购买车票、预订酒店或承诺实时价格。公开平台、地图和 12306 页面可能要求登录或限制访问；无法核实的内容须在报告里标为待核实。
