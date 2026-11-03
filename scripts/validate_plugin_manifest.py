"""Validate that plugin.json names files and entrypoints in this checkout.

The JSON schema is shipped for editors. This command is standard-library-only,
so a broken package fails CI without requiring an optional schema dependency.
"""

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def _is_file(root, relative):
    if not isinstance(relative, str) or not relative:
        return False
    target = (root / relative).resolve()
    return target.is_relative_to(root.resolve()) and target.is_file()


def _is_dir(root, relative):
    if not isinstance(relative, str) or not relative:
        return False
    target = (root / relative).resolve()
    return target.is_relative_to(root.resolve()) and target.is_dir()


def validate_manifest_data(data, root):
    errors = []
    if not isinstance(data, dict):
        return ["plugin.json must contain an object"]

    schema = data.get("$schema")
    if not _is_file(root, schema):
        errors.append("$schema must point to an existing file in the repository")
    else:
        try:
            schema_data = json.loads((root / schema).read_text(encoding="utf-8"))
            if not isinstance(schema_data, dict) or schema_data.get("type") != "object":
                errors.append("plugin.schema.json must define an object schema")
        except (OSError, ValueError) as exc:
            errors.append("plugin.schema.json is invalid: " + str(exc))

    for field in ("name", "entry_skill", "agent"):
        if not isinstance(data.get(field), str) or not data[field]:
            errors.append(field + " must be a nonempty string")
    if not isinstance(data.get("version"), str) or not re.fullmatch(r"\d+\.\d+\.\d+", data["version"]):
        errors.append("version must be major.minor.patch")

    skills = data.get("skills")
    if not isinstance(skills, list) or not skills or not all(isinstance(s, str) and SAFE_NAME.fullmatch(s) for s in skills):
        errors.append("skills must be a nonempty array of safe names")
        skills = []
    if len(skills) != len(set(skills)):
        errors.append("skills contains duplicates")
    actual = {path.parent.name for path in (root / "skills").glob("*/SKILL.md")}
    if set(skills) != actual:
        errors.append("skills differs from checked-in SKILL.md directories: missing="
                      + str(sorted(actual - set(skills))) + ", extra=" + str(sorted(set(skills) - actual)))
    if data.get("entry_skill") not in skills:
        errors.append("entry_skill is absent from skills")
    for skill in skills:
        if not _is_file(root, "skills/{}/SKILL.md".format(skill)):
            errors.append("missing skill entrypoint: " + skill)

    orchestration = data.get("orchestration")
    if not isinstance(orchestration, dict):
        errors.append("orchestration must be an object")
    else:
        for field in ("main_flow", "post_delivery"):
            flow = orchestration.get(field)
            if not isinstance(flow, list) or (field == "main_flow" and not flow):
                errors.append("orchestration." + field + " must be a list")
                continue
            for skill in flow:
                if skill not in skills:
                    errors.append("orchestration." + field + " names unknown skill: " + str(skill))

    agent = data.get("agent")
    if isinstance(agent, str):
        if not SAFE_NAME.fullmatch(agent):
            errors.append("agent must be a safe name")
        elif not _is_file(root, "agents/" + agent + ".md"):
            errors.append("missing agent definition: " + agent)

    rag = data.get("rag")
    if not isinstance(rag, dict):
        errors.append("rag must be an object")
    else:
        if not _is_dir(root, rag.get("index_dir")):
            errors.append("rag.index_dir is missing")
        for field in ("build_script", "validate_script", "retrieve_script"):
            if not _is_file(root, rag.get(field)):
                errors.append("rag." + field + " is missing")
        if not isinstance(rag.get("embedding_model"), str) or not rag["embedding_model"]:
            errors.append("rag.embedding_model is missing")
        if type(rag.get("top_k")) is not int or rag["top_k"] < 1:
            errors.append("rag.top_k must be a positive integer")

    shared = data.get("shared_tools")
    if not isinstance(shared, dict):
        errors.append("shared_tools must be an object")
    else:
        module = shared.get("module")
        if not isinstance(module, str) or not SAFE_NAME.fullmatch(module) or not _is_file(root, module + "/__init__.py"):
            errors.append("shared_tools.module is missing")
        for field in ("contract_document", "openapi", "requirement_agent"):
            if not _is_file(root, shared.get(field)):
                errors.append("shared_tools." + field + " is missing")
        if not isinstance(shared.get("auto_registered"), bool):
            errors.append("shared_tools.auto_registered must be a boolean")
    return errors


def validate_manifest(root=ROOT):
    try:
        data = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["cannot read plugin.json: " + str(exc)]
    return validate_manifest_data(data, root)


def main():
    errors = validate_manifest()
    print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=True, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
