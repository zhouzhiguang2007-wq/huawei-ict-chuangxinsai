"""Run the existing standalone tests and shared interface tests without extra packages."""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    commands = [[sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]]
    commands += [[sys.executable, str(path)] for path in sorted(ROOT.glob("skills/*/scripts/test_*.py"))]
    commands.append([sys.executable, "rag/scripts/validate_skill_manifest.py"])
    failed = 0
    for command in commands:
        print("Running " + " ".join(command[1:]), flush=True)
        failed += subprocess.run(command, cwd=ROOT).returncode != 0
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
