# 项目共享接口与用户偏好记忆

本文件是九个 Skill 及后续 Agent 的统一交接规范。数据库只保存明确确认的长期偏好；需求分析理解用户表达，主编排合并需求并分发同一份快照。Python 3.9+，运行与测试均仅使用标准库。现有各业务脚本和其原生 JSON 保持可用。

## 安装与运行位置

保留完整仓库，在仓库根执行 `python -m travel_shared`。SQLite 默认位于当前宿主用户的 `~/.travel-planner/preferences.sqlite3`；可通过 `--db` 或环境变量 `TRAVEL_PREFERENCES_DB` 指定持久化磁盘上的绝对路径。所有调用使用同一个路径。

码道仍可平铺加载九个 Skill，但共享功能还需要保留仓库中的 `travel_shared/` 和 `docs/`。宿主将 `TRAVEL_SHARED_ROOT` 配置为完整仓库的绝对路径；平铺后的相对文档链接失效时，从该目录读取 `docs/shared-interface.md`，并在该目录运行工具。该环境变量是宿主路径约定，不会自动安装或注册工具。仅复制 Skill 文件夹不能安装共享工具。

AgentArts 云端节点不能访问开发者电脑路径。云端需访问下面的 HTTP 后端，或在拥有持久化磁盘的可信后端导入 `travel_shared.tools.main`。各 Agent 使用统一接口即可，无需各自保存数据库副本。

## 统一工具请求与响应

本地入口：`python -m travel_shared --user-id demo-alice request.json`，省略文件时读取标准输入。`--user-id` 是本地可信操作者参数；云端身份必须来自后端认证，不从用户文本或模型输出提取。

请求 `action` 有六种：

| action | 其他输入 | 行为 |
|---|---|---|
| get | 无 | 返回当前用户的偏好与来源、更新时间 |
| update | preferences、confirmed=true、source | 部分更新长期偏好；整个请求校验通过才写入 |
| delete | fields 非空字段名数组 | 删除指定偏好，重复删除成功且计数为0 |
| clear | 无 | 清空当前用户偏好 |
| prepare | context | 合并偏好、创建/复用快照、生成模块字段映射提示 |
| invoke | context | 先 prepare，再执行支持的确定性计算脚本 |

示例，数据为虚构演示：

```json
{"action":"update","preferences":{"pace":"relaxed","interests":["自然风景"],"photo_styles":["胶片"]},"confirmed":true,"source":"用户明确说：请记住我长期喜欢慢节奏、自然风景和胶片风拍照。"}
```

统一响应：

```json
{"schema_version":"1.0","action":"get","status":"ok","data":{"preferences":{},"metadata":{}},"warnings":[],"errors":[]}
```

顶层 `status` 仅表示工具调用：`ok`、`invalid`、`unavailable`。业务计算结果放在 `data.result`，保留原始 `status/ready/valid` 等字段。顶层 `ok` 不等于行程通过；例如 `data.result.status=fail` 必须回到修正流程。

CLI 输出 UTF-8 JSON（包括 Windows 默认 GBK 终端），退出码为0、2、3。HTTP 对应200、400、503，身份认证失败401、只读凭据请求写操作返回403。业务失败不更改工具调用状态。

## 统一交接 context

```json
{
  "schema_version":"1.0",
  "trip_id":"demo-trip-001",
  "skill":"travel-accommodation-advisor",
  "requirements":{
    "destination":{"city":"贵阳"},
    "dates":{"start_date":"2027-02-01","days":2},
    "travelers":{"total":2,"adults":2},
    "budget":{"amount":3000,"currency":"CNY","scope":"total_trip","hard_limit":true},
    "preferences":{"pace":"balanced"}
  },
  "trip_preferences":{},
  "explicit_preference_fields":[],
  "payload":{}
}
```

- `requirements` 沿用需求分析的完整对象，本例为简写，完整行程须通过需求校验。已有 AgentArts `requirements_json` 在可信宿主解析一次放入此字段，避免多层 JSON 字符串。
- `trip_id` 由宿主生成并在同一行程中保持不变；工具不持久化行程、对话或进度。
- `skill` 使用 `plugin.json` 中九个现有名称，改成 Agent 后仍可保留这些路由标识。
- `payload` 是目标计算脚本原生输入，不在共享工具中猜测缺失路线、报价、证据、订单或固定活动。
- `prepare` 返回 `data.context` 和 `data.input_hints`。映射提示用于构建相应模块输入，不会自动覆盖 `payload`；复核的已确认硬约束在 `invoke` 中会实际覆盖原案和草案的对应要求。
- 单个 Skill 独立使用时，宿主同样先 `prepare`，仅询问该任务需要的条件。

### 偏好字段与合并规则

| 字段 | 类型/值 |
|---|---|
| interests | 兴趣字符串数组 |
| pace | relaxed / balanced / intensive / unspecified |
| transport_modes | walk / transit / drive / bike / mixed / unspecified 数组 |
| walking_tolerance_minutes | 非负整数分钟，属于偏好，不等于每日硬距离限制 |
| accommodation | 住宿喜好字符串数组 |
| photo_styles | 拍照风格字符串数组 |
| photo_social_preference | strangers_ok / companions_only / no_interaction / unspecified |

优先级：`requirements.preferences` 本轮明确值 > `trip_preferences` 本次已确认值 > SQLite 长期偏好。列表整体替换，不自动拼接；这样本轮“只想看展”不会保留历史美食偏好。

缺失、null、unspecified 和默认空数组表示未知，继承较低优先级的值。用户明确说“这次无兴趣限制”时，将 `interests: []` 并把 `interests` 加入 `explicit_preference_fields`，才能显式清空本次偏好。`0` 分钟是有效明确值。长期偏好的删除使用 delete/clear，不通过 null 隐式删除。

主编排首次 prepare 取得 `preference_snapshot`，其中有合并后的偏好、逐字段 origins（memory/trip/current）、memory_status 和服务端封签 `seal`。封签绑定可信 user_id 与 trip_id；下游只能修改 skill/payload 后复用同一 context，不能编辑快照。篡改、跨用户或跨行程复用会返回 invalid。多个后端实例或多次独立 CLI 调用要在受保护的宿主配置中共用至少 32 字节的 `TRAVEL_SNAPSHOT_SECRET`；未配置时每个进程生成临时随机密钥，只能在同一进程内复用快照。密钥不能传给模型、用户文本或浏览器前端。

用户开始新一轮修改需求或切换用户时，宿主丢弃旧快照，以原始本次偏好重新 prepare。不能把上轮已经合并的全部偏好冒充本轮明确输入；宿主应保留原始需求与本次确认值。快照由可信宿主维护，不接受网页、用户或模型伪造的快照。

### 字段映射

| 模块 | 映射规则 |
|---|---|
| 需求分析 / 资料与路线规划 | 使用合并后的 requirements.preferences；偏好不能补齐日期、预算和人数 |
| 住宿 | 传目的地、入住候选日、成人数和住宿喜好；退房日、房数、儿童年龄、住宿预算单独确认 |
| 拍照 | 传风格与社交偏好；当前拍摄人数、关系、地点和光线重新按任务确认 |
| 复核 / 重排 | 仅已确认硬约束写入 requirements.review_requirements，再映射为 plan.requirements；不从一般偏好推断硬约束 |
| 空档推荐 | 按偏好筛选，再用当前起终点、硬截止和地图事实计算可行性 |
| 手册 | 读取最终行程；默认不导出用户标识、偏好来源和完整档案 |

预算 `amount` 是主币单位；费用脚本 `amount_minor` 为最小币单位。只自动转换 `scope=total_trip` 且 `hard_limit=true` 的预算；CNY/USD/EUR/GBP/HKD乘100，JPY乘1，精度不符或币种未支持则报 invalid，不四舍五入。每人/每天预算须明确覆盖范围后转换，旅行总预算不直接当住宿专项预算。

步行分钟不自动换算每日米数；交通喜好不自动变成 allowed_transport_modes；必去地点名须解析为公共地点 ID 后才能进入 mandatory_place_ids。`review_requirements` 只放用户确认的硬约束，不能由长期记忆自动生成。

### 确定性脚本调用

`invoke` 支持：需求校验、完整路线校验、住宿费用比较、行程复核、空档可行性计算。需求校验直接使用合并后的 requirements；其余使用 payload（复核额外应用上述硬约束映射）。共享接口复核时**总是**以可信后端当前时间覆盖 payload 中的 `as_of`，防止模型把时钟改到过去而放行已错过的活动；单独直接调用原复核脚本时由调用方负责传可信时间。

主编排与拍照属于模型工作流，只支持 prepare。重排先 prepare，再按现有 `replan_guard.py` 接口调用，保留原版进度、事件、冻结活动和版本检查；将已确认映射通过现有 requirement_updates 流程确认，不能绕过该流程直接改旧计划。手册先 prepare，再按现有 CLI 生成文件。共享 invoke 不生成图片、不写手册文件、不自动执行 LLM、不自动注册平台工具。

## Agent 的调用职责

1. 主编排从可信宿主取得身份与 trip_id，读取记忆并建立偏好快照。对用户简要说明沿用的历史偏好，允许本次覆盖。
2. 需求分析识别“这次”与“以后都这样”。推测只生成待确认提问；用户明确要求记住或确认长期保存后，才由可信宿主提交 update，source 记录确认依据。confirmed 是宿主决策，不能因模型猜测就填 true。
3. 本次预算、日期、人数、同行关系、天气、位置和临时体力不写入长期偏好。明确长期拍照社交偏好可记录，但不据此推断心理健康状况。
4. 主编排把同一 context 快照分发给各 Agent，分别构造 payload，并核对业务结果。手册只接收最终交付数据。
5. get/delete/clear 响应成功后才告知“已读取/删除”；update 失败明确说“未保存”。prepare 读取失败仍使用本次输入继续问答，并在 warnings 说明。

## HTTP 与 AgentArts 接入

PowerShell 本地示例：

```powershell
# token 与快照密钥使用随机值；示例标记须替换，只保留在后端受保护配置。
$env:TRAVEL_TOOL_TOKENS='{"replace-with-read-token":"demo-alice","replace-with-write-token":{"user_id":"demo-alice","allow_memory_write":true}}'
# TRAVEL_SNAPSHOT_SECRET 必须为至少 32 字节的随机密钥，跨实例/重启复用快照时各实例保持一致。
python -m travel_shared.server --db ./data/preferences.sqlite3
```

后端只提供 `POST /v1/tools`，Body 为上述请求 JSON，认证头 `Authorization: Bearer <token>`。服务端按 token 查用户身份，拒绝请求中的 user_id。简单的 `token: user_id` 条目**默认只读**，可用于 get/prepare/invoke；update/delete/clear 返回 403。只有显式 `{"user_id":"...","allow_memory_write":true}` 的写凭据才能修改长期偏好；写凭据应由已验证用户确认的可信后端持有，不能配置给可由模型自行调用的工具。`confirmed=true` 与 source 仍需由可信后端依据真实用户确认提交，不能由模型或网页自行声称。token 表适合受控 Demo；真实多用户应用由登录后端确定身份并调用 Python 接口，不能让所有用户共用一个固定身份 token。密钥放在平台工具的受保护配置中，不写进提示词、浏览器前端或仓库。

默认监听127.0.0.1，仅供本机验证。云端通过可达 HTTPS 入口和可信代理接入，将数据库放在同一台后端的持久化磁盘；不要把 db 放进无持久化的函数临时目录，也不要让多台机器直接共享打开 db 文件。服务使用短事务和5秒锁等待，低频写入使用 SQLite 默认日志模式。大规模多实例部署再迁移数据库，调用方接口保持不变。

在 AgentArts 的工具配置中填写后端 HTTPS 地址、POST、JSON 请求及认证头，或依据 `contracts/tools.openapi.json` 导入（是否支持导入以实际控制台为准）。如平台只支持标量输入输出，可信后端调用 `travel_shared.tools.main({"request_json":"..."}, user_id=authenticated_user, db_path=...)`，得到 status/result_json；该桥接默认拒绝长期偏好写入。用户在可信后端确认长期保存/删除后，后端才单独传 `allow_memory_write=True`。不要把该参数或 user_id 暴露成模型可填字段。仓库不代替控制台完成注册、鉴权配置、云部署或 Demo 页面搭建。

## 验收

运行 `python scripts/run_checks.py`：包括共享工具与 HTTP 联调、原有全部独立脚本测试和 Skill 清单校验。`examples/shared-tools/` 是模拟请求，可按 update → prepare → get → clear 顺序本地试跑。

平台验收：同一用户新会话仍记住；不同用户隔离；“这次快节奏”不覆盖长期慢节奏；改变长期偏好后下一轮生效；一轮多 Agent 快照一致；删除后新快照不再复用；数据库不可用继续问答但不宣称保存；演示复核失败时不交付为可执行行程。工具测试不能代替平台实际模型调用和部署验证。
