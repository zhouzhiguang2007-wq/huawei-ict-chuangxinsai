# 码道中的铁路主动查询：接线与验收

## 为什么只导入 Skill 不够

`multi-platform-travel-planner` 定义查询规则，但不能凭文本直接操作 12306。仓库中的 `agents/travel-planner.md` 已允许 `webfetch`、`websearch`；12306 的日期和站点交互通常还需要可操作网页的连接器。高德 MCP 只能查车站位置与接驳，不提供可作为 12306 官方证据的列车、票价或余票。

## 在码道桌面端接线

1. 打开“扩展 > 连接器”，查找可控制浏览器的连接器并安装；新任务输入框中确认已添加。码道 IDE 用户可在“设置 > MCP 工具 > 市场”安装 Playwright MCP。连接器名称和配置入口以当前客户端界面为准。
2. 如果使用项目自定义智能体，检查其 MCP 工具权限，确保所安装的浏览器工具对该智能体可见。重启或刷新智能体后，先单独测试：打开铁路 12306 官方查询页面，选择一个未来日期及起终站，读取真实查询结果和查询时间。
3. 再导入或更新本仓库的 Skill 与 `agents/travel-planner.md`。只更新 GitHub 不会自动替换码道里已缓存的旧版本。
4. 在 AgentArts 部署时重新配置对应的浏览器/HTTP/插件能力；码道本机 MCP 配置不会自动成为 AgentArts 云端工作流的工具。

参考：

- 华为云码道连接器：https://support.huaweicloud.com/usermanual-codeartsdesktop/desktop_0015.html
- 码道 IDE MCP：https://support.huaweicloud.com/usermanual-codeartsagent/codeartsagent_ug_0010.html
- 码道自定义智能体工具权限：https://support.huaweicloud.com/usermanual-codeartsagent/codeartsagent_ug_0051.html
- 官方 12306 查询入口：https://mobile.12306.cn/weixin/wxcore/init

## 回归测试

用新会话给出两城往返旅行，明确未来出发和返程日期、起终点与可出发时段，但不要说“请查车票”。预期：智能体先自动尝试官方 12306 往返查询；成功时列实际起终站、车次、时刻、查询时间与来源；失败时说明 `tool_unavailable`、`blocked`、`no_result` 或需澄清的站点，不出现看似确定的占位车次和时刻。

另测两个分支：

- 只给日期、不说可出发时段：先查官方全天候选，再追问可出发时段，不直接选清晨车次。
- 浏览器工具缺失或官方页面要求人工验证：说明能力限制，保留返程时刻、票价和余票为未知，不要求游客重复提醒查询，也不绕过登录或验证码。

不要将官方页面的访问失败伪装成“已查询无车”。不要记录乘车人姓名、证件号码或支付信息。
