"""安装版本自检：比对仓库与宿主已安装的 skill 副本。

覆盖整个 skill 目录（SKILL.md、references、scripts 等），
不再只比对单个文件，避免 references/scripts 静默漂移。

用法：
    python scripts/check_install.py <本地 skills 安装目录>

退出码：
    0  全部一致
    1  存在差异或未安装
    2  参数缺失或目录不存在

只做只读比对，不修改任何文件；输出 SKILL 文件 SHA-256 前 12 位便于排查。
纯标准库，Python 3.9+。
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HASH_LEN = 12

EXCLUDE_DIRS = {"__pycache__", ".pytest_cache"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}

USAGE = "用法：python scripts/check_install.py <本地 skills 安装目录>"


def sha12(path):
    """返回文件 SHA-256 前 12 位；文件不存在时返回 None。"""
    path = Path(path)
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()[:HASH_LEN]


def load_manifest(root=ROOT):
    with open(Path(root) / "plugin.json", "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    return manifest["version"], list(manifest["skills"])


def _iter_skill_files(skill_dir):
    skill_dir = Path(skill_dir)
    files = []
    for item in sorted(skill_dir.rglob("*")):
        if not item.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in item.parts):
            continue
        if item.suffix in EXCLUDE_SUFFIXES:
            continue
        files.append(item.relative_to(skill_dir))
    return files


def check(install_dir, root=ROOT):
    """比对仓库与安装目录，返回 (version, comparisons)。

    comparisons 每项为 (skill, relative_path, status)：
        status = "same" / "diff" / "missing_install" / "missing_repo"
    """
    version, skills = load_manifest(root)
    install_dir = Path(install_dir)
    comparisons = []

    for skill in skills:
        repo_dir = Path(root) / "skills" / skill
        installed_dir = install_dir / skill
        repo_files = _iter_skill_files(repo_dir) if repo_dir.is_dir() else []
        relative_paths = sorted(set(repo_files) | set(
            _iter_skill_files(installed_dir) if installed_dir.is_dir() else []),
            key=str)

        if not repo_files and not installed_dir.exists():
            comparisons.append((skill, "SKILL.md", "missing_repo"))
            continue
        if not relative_paths:
            comparisons.append((skill, "SKILL.md", "missing_install"))
            continue

        for relative in relative_paths:
            repo_hash = sha12(repo_dir / relative)
            installed_hash = sha12(installed_dir / relative)
            if installed_hash is None:
                status = "missing_install"
            elif repo_hash is None:
                status = "missing_repo"
            elif repo_hash == installed_hash:
                status = "same"
            else:
                status = "diff"
            comparisons.append((skill, str(relative).replace("\\", "/"), status))

    return version, comparisons


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print(USAGE)
        return 2

    install_dir = Path(argv[0])
    if not install_dir.is_dir():
        print(USAGE)
        print("安装目录不存在：{}".format(install_dir))
        return 2

    version, comparisons = check(install_dir)
    problems = [(skill, name, status) for skill, name, status in comparisons
                if status != "same"]

    print("仓库版本: {}".format(version))
    print("比对文件: {}".format(len(comparisons)))
    if not problems:
        print("全部一致")
        return 0

    print("差异 ({}):".format(len(problems)))
    for skill, name, status in problems:
        if status == "missing_install":
            print("  - {}/{} (未安装)".format(skill, name))
        elif status == "missing_repo":
            print("  - {}/{} (仓库缺失)".format(skill, name))
        else:
            print("  - {}/{}".format(skill, name))
    print("提示：先同步 9 个 skill 目录后再使用，否则问卷/拍照等能力可能静默缺失。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())