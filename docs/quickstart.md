# 环境复现与启动顺序

本文固定依赖与启动配置，保证换一台机器能复现同一套行为。

## 1. 运行环境

| 组件 | 要求 | 说明 |
|---|---|---|
| Python | 3.9+ | CI 在 3.9 与 3.13 上同时验证 |
| 核心功能 | 仅标准库 | `travel_shared`、9 个 skill 的业务脚本、全部测试 |
| 本地 RAG（可选） | `pip install -r requirements-rag.txt` | 仅 `rag/build_index.py` / `rag/retrieve.py` 需要；未装不影响其他功能 |
| 铁路 MCP（可选） | Node.js 18+ | `npx -y 12306-mcp`；未装则铁路查询降级 |

## 2. 环境变量

| 变量 | 作用 | 默认 |
|---|---|---|
| `TRAVEL_INTERNAL_DB` | 内部私有库路径（知识/会话/问卷/偏好同库） | `~/.travel-planner/internal.sqlite3` |
| `TRAVEL_PREFERENCES_DB` | 偏好库路径；设置后偏好与内部库分离 | 跟随 `TRAVEL_INTERNAL_DB` |
| `TRAVEL_SHARED_ROOT` | 码道平铺加载时指向完整仓库根 | 无 |

初始化与运行时必须使用同一个 `TRAVEL_INTERNAL_DB`。

## 3. 启动顺序

```bash
# 1) 初始化内部库（幂等，可重复执行）
python -m travel_shared.seed_knowledge

# 2) 旧偏好迁移（有旧 preferences.sqlite3 时；先 dry-run 看统计）
python scripts/migrate_preferences.py --dry-run
python scripts/migrate_preferences.py

# 3) 安装自检（9 个 skill 是否与仓库一致）
python scripts/check_install.py ~/.workbuddy/skills

# 4) 铁路 MCP 自检（可选）
python scripts/check_mcp.py

# 5) 代码层闭环自检
python scripts/e2e_smoke.py

# 6) 全量检查（CI 同款）
python scripts/run_checks.py

# 7) 本地 RAG（可选）
python -m pip install -r requirements-rag.txt
python rag/build_index.py
python rag/retrieve.py "住宿比价 位置 房型"
```

## 4. 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| `status=unavailable`、`reason=db_not_seeded` | 内部库未初始化 | 执行第 1 步；确认 `TRAVEL_INTERNAL_DB` 与运行时一致 |
| 偏好“消失” | 旧 `preferences.sqlite3` 未迁移 | 执行第 2 步，确认目标库为内部库 |
| 安装自检报差异/未安装 | 宿主 skills 副本过旧 | 同步 9 个 skill 目录后重跑第 3 步 |
| 铁路段全是未知 | 未装 12306-mcp 或握手失败 | 跑第 4 步定位；按 `docs/12306-mcp-setup.md` 配置 |
| RAG 检索报缺少模型 | 未装可选依赖 | 执行第 7 步前半段 |

## 5. 验证基线

- `scripts/run_checks.py` 退出码 0
- `scripts/check_install.py` 输出 `全部一致`
- `scripts/e2e_smoke.py` 输出 `全部通过`
- `scripts/check_mcp.py` 输出 `状态: ok`（装了 12306-mcp 时）