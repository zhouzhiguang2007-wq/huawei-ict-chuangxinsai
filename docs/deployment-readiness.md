# 部署与联调说明

本文从仓库文件到本地调用，再到 AgentArts 工具注册，列出实际需要完成的步骤。接口字段与偏好合并规则以[共享接口](shared-interface.md)为准；九个 Skill 的加载路径见[Skills 说明](../skills/README.md)。

## 1. 仓库与索引

在完整仓库根运行 `python scripts/run_checks.py`。该命令核对插件清单、Skill 文件与链接、业务脚本、共享工具，并检查 `rag/index/` 是否匹配当前 Skill 与公共文档。若索引过期，在文本修改结束后运行 `python -m pip install sentence-transformers numpy pyyaml`、`python rag/build_index.py`，再运行 `python rag/scripts/validate_index.py`。模型已在本地缓存时可用 `python rag/build_index.py --offline`。构建完成后，检索示例是 `python rag/retrieve.py "开封两天完整线路"`。

索引含公共操作规范，不包含用户数据库。每次变更 Skill 或 `docs/` 后都要重建并提交 `rag/index/` 的三个文件。验证脚本只依赖标准库；构建和检索需要模型依赖与本地模型缓存。

## 2. 本地 CodeArts

保留完整仓库，并把九个 Skill 文件夹平铺到 `C:\Users\<你>\.codeartsdoer\cache\user\skills\`，Agent 定义放到同级 `agents\`。宿主把 `TRAVEL_SHARED_ROOT` 设为完整仓库的绝对路径，在该目录启动 RAG 与共享工具。平铺后的 Skill 文件夹不能代替仓库根，`TRAVEL_SHARED_ROOT` 只是路径约定，不会自行安装或注册工具。

在本地运行一次只读请求，确认工具可导入：

```powershell
$env:TRAVEL_SHARED_ROOT = (Get-Location).Path
python -m travel_shared --db .\data\demo.sqlite3 --user-id demo-alice examples/shared-tools/get.json
```

演示数据库位于被 Git 忽略的 `data/`。CLI 的 `--user-id` 是本地可信操作者输入；在联网应用中，身份必须来自登录后端，不能取自模型输出或请求正文。CodeArts Agent 定义的 `mcp_tools: {}` 是空配置，需由宿主显式接入工具后才能读写长期偏好。只有普通规划需求时，可以使用 Skill 原文和 references；未接通共享工具或 RAG 时不能报告已经调用成功。

## 3. 可信后端的配置

长期偏好 SQLite 使用 `TRAVEL_PREFERENCES_DB` 或 CLI/服务端 `--db` 指向持久化磁盘上的绝对路径。多个工具调用必须指向同一数据库。多次独立进程或多个实例复用本次 `preference_snapshot` 时，设置同一个至少 32 字节的随机 `TRAVEL_SNAPSHOT_SECRET`；不设置时密钥按进程临时生成，跨进程快照无法验证。密钥只放在后端的受保护配置中。

HTTP 适配器通过 `TRAVEL_TOOL_TOKENS` 将令牌映射到可信用户。字符串形式的普通令牌只读；具有 `allow_memory_write: true` 的令牌可执行 update/delete/clear，必须只由验证用户确认的可信后端持有，不能直接暴露给模型工具或浏览器。`confirmed=true` 与 `source` 也须由该后端据真实确认提交，不能仅凭模型声称。真实多用户服务应由登录后端确定用户身份，示例令牌表只供受控联调。详细请求、响应、权限和服务启动命令见[共享接口的 HTTP 章节](shared-interface.md#http-与-agentarts-接入)。

本地联调可依次验证同一用户再次 get 能读到确认的偏好、另一用户 get 为空、本次偏好覆盖长期偏好但不改数据库、删除后新快照不再读到旧值、数据库不可用时明确提示未保存。`prepare` 返回的快照有服务端封签，下游复用同一份 context；修改偏好或行程后丢弃旧快照重新 prepare。共享接口的 `status=ok` 只表示工具调用成功，正式交付还要检查 `data.result` 中的业务结果。

## 4. AgentArts 云端注册

将完整代码部署到可信后端，提供可从 AgentArts 到达的 HTTPS `POST /v1/tools`，或者在可信后端调用 `travel_shared.tools.main` 并封装为平台支持的工具。根据 `contracts/tools.openapi.json` 配置工具输入、返回 JSON 与认证头；控制台是否支持 OpenAPI 导入以目标工作空间为准。为各 Agent 配置同一个后端服务和用户身份来源，不在云端直接引用开发者电脑的路径。

云端还需配置持久化数据库、快照密钥、HTTPS 与工具鉴权，并在目标 Agent 工作流中实际注册和授权调用。AgentArts 的登录、目标项目与工作空间、网络地址和受保护配置都属于平台部署步骤；将代码推送到 GitHub 或复制本地 Skill 不会自动完成它们。平台注册后再用真实模型会话验证需求分析、完整逐日线路、拍照、住宿、复核和手册串联，以及跨会话偏好和用户隔离。
