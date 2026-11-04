"""Run all repository, Skill, plugin and RAG checks.

Install the test-only dependency first: python -m pip install pytest
"""

import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    if importlib.util.find_spec("pytest") is None:
        print("Full checks require pytest; run: python -m pip install pytest",
              file=sys.stderr)
        return 2
    commands = [[sys.executable, "-m", "pytest", "tests", "-q"]]
    commands += [[sys.executable, str(path)] for path in sorted(ROOT.glob("skills/*/scripts/test_*.py"))]
    commands.append([sys.executable, "scripts/validate_plugin_manifest.py"])
    commands.append([sys.executable, "rag/scripts/validate_skill_manifest.py"])
    commands.append([sys.executable, "rag/scripts/validate_index.py"])
    failed = 0
    for command in commands:
        print("Running " + " ".join(command[1:]), flush=True)
        failed += subprocess.run(command, cwd=ROOT).returncode != 0
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
