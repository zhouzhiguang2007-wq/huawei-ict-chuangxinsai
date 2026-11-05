# 接入 12306 MCP（铁路车次/余票/票价）

`12306-mcp` 是社区实现（非官方 MCP），通过读取 12306 官方查询页面数据结构返回车次、时刻、历时、席别、票价和余票。它能显著补齐插件在铁路环节的空缺，但结果仍需标注来源并以官方页面为准。

## 1. 选用哪个实现

| 实现 | 语言 | 安装 | 说明 |
|------|------|------|------|
| [Joooook/12306-mcp](https://github.com/Joooook/12306-mcp)（npm `12306-mcp`） | TypeScript | `npx -y 12306-mcp` | 推荐。2.4k stars，月下载约 3 万，`0.3.10` 版本，stdio/http 双模式，MIT |
| [drfccv/mcp-server-12306](https://github.com/drfccv/mcp-server-12306) | Python | 自建虚拟环境 | 备选，功能相近 |

本仓库以 `12306-mcp` 为准编写文档和 skill 规则。

**运行要求**：Node.js 18+（`npx` 可用）。仅用 stdio 模式时不需要 Docker。

## 2. 客户端配置

码道桌面端：`设置 / 扩展 > MCP 工具 > 添加`，或直接编辑 MCP 配置文件加入：

```json
{
  "mcpServers": {
    "12306-mcp": {
      "command": "npx",
      "args": ["-y", "12306-mcp"]
    }
  }
}
```

需要 HTTP 模式（供 AgentArts 或远程调用）时：

```bash
npx -y 12306-mcp --port 8080
```

配置后重启或刷新自定义智能体，确认该 MCP 的工具对 `travel-planner` agent 可见。

## 3. 可用工具

| 工具 | 作用 |
|------|------|
| `get-current-date` | 取上海时区当前日期（解析“明天/下周三”） |
| `get-stations-code-in-city` | 按城市名列出该城市全部车站及 `station_code` |
| `get-station-code-of-citys` | 按城市名取代表站 `station_code`，多城市用 `\|` 分隔 |
| `get-station-code-by-names` | 按车站名取 `station_code`，如“北京南\|上海虹桥” |
| `get-station-by-telecode` | 按 3 位电报码查车站详情 |
| `get-tickets` | 余票查询：日期、起终站、车次类型筛选（G/D/Z/T/K/O/F/S）、出发时段、排序 |
| 过站/中转查询 | 列车经停站与中转换乘方案 |

`get-tickets` 关键参数：`date`（`yyyy-MM-dd`）、`fromStation`、`toStation`、`trainFilterFlags`（如 `G` 只看高铁）、`earliestStartTime`/`latestStartTime`（0-24）、`sortFlag`。

## 4. 验证（不安装 Skill 也能单独测）

```bash
npx -y 12306-mcp
```

期望输出 `12306 MCP Server running on stdio`。随后在智能体里发一条测试请求：

> 帮我查 2026-11-10 洛阳到开封的高铁

预期：先调 `get-station-code-by-names` 解析车站，再调 `get-tickets`，返回真实车次（如 G1812 洛阳龙门 08:05→开封北 09:12）、席别、票价和余票，并给出查询时间。

仓库内已验证结果示例（2026-11-05 查询 2026-11-10 洛阳→开封，`trainFilterFlags=G`）：

```
G1812 洛阳龙门 -> 开封北 08:05 -> 09:12 历时 01:07  二等座 有票 91 元
G2260 洛阳龙门 -> 开封北 11:16 -> 12:19 历时 01:03  二等座 有票 91 元
G1880 洛阳龙门 -> 开封北 18:04 -> 19:05 历时 01:01  二等座 有票 80 元
```

## 5. 使用规则（与 skill 保持一致）

1. 日期、起终点齐全才查询；缺日期先问，或用 `get-current-date` 换算相对日期。
2. 时段不明时先查全天，再向用户确认可出发时段，不把清晨车次当默认。
3. 城市名先经 `get-station-code-of-citys` / `get-station-code-by-names` 解析，核对起终站是否为用户要的具体车站。
4. 记录 `lookup_status`（`verified`/`no_result`/`blocked`/`tool_unavailable`/`needs_station_clarification`）、`queried_at`、车站对。
5. 余票与票价会变动，输出必须写查询时间并提示以 12306 官方结算为准。
6. 不自动登录、不填写乘车人证件、不提交订单或支付。

## 6. 边界与风险

- 社区实现依赖 12306 页面结构，接口变更或反爬升级时可能失效；失效时降级为浏览器工具或记录 `tool_unavailable`，不得伪造车次。
- 高德 MCP 只解决车站位置与接驳，不能替代本 MCP 提供铁路证据。
- 码道本机 MCP 配置不会自动同步到 AgentArts 云端工作流，云端需另行注册工具或部署 HTTP 模式后端。