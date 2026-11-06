"""生成可分发的插件压缩包。

用法：
    python scripts/export_plugin.py
    python scripts/export_plugin.py --include-rag-index
    python scripts/export_plugin.py --output dist/custom.zip

默认排除版本库、缓存、本地数据库与 RAG 索引（索引按需重建）。
纯标准库。
"""

import argparse
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".sqlite3", ".sqlite3-wal", ".sqlite3-shm"}
EXCLUDE_FILES = {".gitignore"}

BASE_ENTRIES = [
    "plugin.json", "plugin.schema.json", "README.md", "LICENSE",
    "CHANGELOG.md", "requirements-rag.txt",
    "agents", "skills", "travel_shared", "contracts", "scripts", "docs", "tests",
]


def _iter_files(path):
    path = Path(path)
    if path.is_file():
        yield path
        return
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in item.parts):
            continue
        if item.suffix in EXCLUDE_SUFFIXES:
            continue
        if item.name in EXCLUDE_FILES:
            continue
        yield item


def collect(include_rag_index=False):
    files = []
    for entry in BASE_ENTRIES:
        target = ROOT / entry
        if not target.exists():
            continue
        files.extend(_iter_files(target))
    files.append(ROOT / "rag" / "build_index.py")
    files.append(ROOT / "rag" / "retrieve.py")
    files.append(ROOT / "rag" / "chunk_strategy.py")
    files.append(ROOT / "rag" / "config.yaml")
    for extra in ("rag/scripts",):
        if (ROOT / extra).exists():
            files.extend(_iter_files(ROOT / extra))
    if include_rag_index:
        files.extend(_iter_files(ROOT / "rag" / "index"))
    # 去重并排序
    seen = set()
    unique = []
    for f in files:
        resolved = f.resolve()
        if resolved in seen or not f.exists():
            continue
        seen.add(resolved)
        unique.append(f)
    return sorted(unique, key=lambda p: str(p.relative_to(ROOT)).lower())


def build(output=None, include_rag_index=False):
    manifest = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    if output is None:
        output = ROOT / "dist" / "travel-planner-plugin-{}.zip".format(version)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    files = collect(include_rag_index=include_rag_index)
    with zipfile.ZipFile(str(output), "w", zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(str(file), str(file.relative_to(ROOT)).replace("\\", "/"))
    return {"output": str(output), "version": version,
            "file_count": len(files), "include_rag_index": include_rag_index}


def main(argv=None):
    parser = argparse.ArgumentParser(description="打包旅行规划插件")
    parser.add_argument("--output", default=None)
    parser.add_argument("--include-rag-index", action="store_true")
    args = parser.parse_args(argv)
    report = build(args.output, args.include_rag_index)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())