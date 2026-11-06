"""从 plugin.json 与 seed 注册表生成 docs/skill-map.md。

保证「skill 关系图」这份交付文档永远与 manifest / 注册表一致，不用手抄。

用法：
    python scripts/render_skill_map.py            # 写入 docs/skill-map.md
    python scripts/render_skill_map.py --stdout   # 打印到标准输出
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from travel_shared.seed_knowledge import SKILL_REGISTRY_DATA  # noqa: E402


def load_manifest(root=ROOT):
    return json.loads((Path(root) / "plugin.json").read_text(encoding="utf-8"))


def render(manifest=None):
    manifest = manifest or load_manifest()
    registry = {entry["skill_name"]: entry for entry in SKILL_REGISTRY_DATA}
    skills = manifest["skills"]
    graph = manifest["skill_graph"]
    edges = graph["edges"]

    upstream = {name: [] for name in skills}
    downstream = {name: [] for name in skills}
    kinds = {}
    for edge in edges:
        downstream.setdefault(edge["from"], []).append(edge["to"])
        upstream.setdefault(edge["to"], []).append(edge["from"])
        kinds.setdefault(edge["from"], []).append(edge["kind"])

    lines = [
        "# 插件 skill 关系图",
        "",
        "> 本文件由 `scripts/render_skill_map.py` 从 `plugin.json` 与 "
        "`travel_shared.seed_knowledge.SKILL_REGISTRY_DATA` 生成，请勿手工修改。",
        "",
        "## 全景",
        "",
        "```",
        "travel-planner-agent",
        "        |",
        "        v",
        "travel-planner-plugin  (编排器)",
        "        |",
        "        +--> travel-requirement-analysis   需求确认 / 引导问卷",
        "        +--> multi-platform-travel-planner 资料核实 / 铁路 / 逐日时间线",
        "        +--> travel-accommodation-advisor  住宿比价",
        "        +--> x-xiake                       拍照出片指导",
        "        +--> travel-plan-review            行程复核",
        "        +--> travel-handbook-builder       离线手册",
        "        +--> travel-replanner              途中重排",
        "        +--> travel-time-pocket            临时空档微行程",
        "```",
        "",
        "所有 skill 通过同一份共享状态协作：`travel_shared`（SQLite 内部私有库 + 24 个 action）。",
        "",
        "## skill 清单",
        "",
        "| Skill | 类别 | 上游 | 下游 | 触发关键词 | 产出 |",
        "|---|---|---|---|---|---|",
    ]
    for name in skills:
        entry = registry.get(name, {})
        category = entry.get("category", "")
        up = "、".join(sorted(set(upstream.get(name, [])))) or "—"
        down = "、".join(sorted(set(downstream.get(name, [])))) or "—"
        keywords = "、".join(entry.get("trigger_keywords", [])) or "—"
        output = entry.get("output_summary", "—")
        lines.append("| `{}` | {} | {} | {} | {} | {} |".format(
            name, category, up, down, keywords, output))

    lines += [
        "",
        "## 共享状态",
        "",
        "| 状态 | 表 | 使用方式 |",
        "|---|---|---|",
        "| 需求与会话上下文 | `session_context` | `session_put` / `session_get`，按 `user_id` 隔离 |",
        "| 旅行常识 | `travel_knowledge` | `knowledge_query`（城市/交通/预算/住宿/美食/机位/季节） |",
        "| 能力注册表 | `skill_registry` | `registry_query` 按触发关键词匹配 skill |",
        "| 引导问卷 | `guided_questions` | `questionnaire_get_step` 逐轮提问，13 步 |",
        "| 用户偏好 | `preferences` | `get` / `update` / `delete` / `clear`，按 `user_id` 隔离 |",
        "",
        "## 调用顺序",
        "",
        "主流程：`" + " → ".join(manifest["orchestration"]["main_flow"]) + "`",
        "",
        "交付后分流：`" + " / ".join(manifest["orchestration"]["post_delivery"]) + "`",
        "",
        "## 依赖边",
        "",
        "| 从 | 到 | 含义 |",
        "|---|---|---|",
    ]
    for edge in edges:
        lines.append("| `{}` | `{}` | {} |".format(
            edge["from"], edge["to"], edge["kind"]))
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="生成 skill 关系图")
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args(argv)
    text = render()
    if args.stdout:
        print(text)
        return 0
    target = ROOT / "docs" / "skill-map.md"
    target.write_text(text, encoding="utf-8")
    print("wrote", target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())