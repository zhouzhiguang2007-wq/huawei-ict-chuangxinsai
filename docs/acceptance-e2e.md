# 端到端闭环验收记录

本文件记录代码层可重复的闭环基线。它证明组件能串起来运行，**不等同于**宿主内的真实对话验收；后者需要人工在码道 / AgentArts 中完成并留证。

## 1. 运行方式

```bash
python scripts/e2e_smoke.py          # 人类可读
python scripts/e2e_smoke.py --json   # 机器可读
python -m unittest tests.test_e2e_smoke -v
```

不联网、不写真实数据库，全部使用临时 SQLite。

## 2. 本次结果（2026-11-06）

```
PASS seed              {'count': 13, 'status': 'bulk_upserted'}
PASS questionnaire.step1  {'dimension': 'destination'}
PASS registry.photo    ['x-xiake', 'travel-planner-plugin']
PASS knowledge.kaifeng {'spots': 6}
PASS session.roundtrip {'city': '开封'}
PASS railway.normalize {'train': 'G1812', 'depart': '08:05'}
PASS railway.segment   {'mode': 'rail'}
PASS route.validate    {'status': 'pass', 'issues': 0}
PASS prepare           {'status': 'ok'}
PASS session.railway   {'verified': 'verified'}
结果: 全部通过
```

## 3. 覆盖链路

| 环节 | 组件 | 断言 |
|---|---|---|
| 初始化 | `travel_shared.seed_knowledge` | 9 个 skill 注册、38 条常识、13 步问卷 |
| 主动引导 | `questionnaire_get_step` | 第 1 步可读，维度 `destination` |
| 能力匹配 | `registry_query` | 「拍照出片」命中 `x-xiake` |
| 领域知识 | `knowledge_query` | 开封景点/美食可查 |
| 会话上下文 | `session_put/get_requirements` | 需求写入并由下游读回（按 user_id 隔离） |
| 铁路数据 | `normalize_railway_mcp` | `get-tickets` 文本 → 结构化 legs，`verified` |
| 路线校验 | `validate_route_timeline` | 构造时间线 `status=pass`，0 issues |
| 偏好合并 | `prepare` | 合法 context 返回 `ok` |
| 下游复用 | `session_put(railway_legs)` | 铁路结果写入会话上下文 |

## 4. 仍需人工完成的验收（P0 剩余部分）

1. 在码道加载 9 个 skill 与 `travel-planner` agent，用一句真实自然语言发起规划。
2. 观察并截图：12/13 步问卷是否实际被逐轮提问、拍照/住宿/复核/手册是否被调用。
3. 在 AgentArts 完成一次平台侧编排与可视化 Demo，保存链接或录屏。
4. 记录每步的工具调用详情（工具名、入参、返回、耗时）。

## 5. 边界

- 本 smoke 使用固定样例车次，不证明实时余票可用；实时部分由 `scripts/check_mcp.py` 与人工联调覆盖。
- `route.validate` 通过只表示结构与时间线自洽，不表示景点当日开放；开放与预约仍需官方来源核实。