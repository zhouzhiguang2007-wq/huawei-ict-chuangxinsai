"""Run the existing standalone tests and shared interface tests without extra packages."""

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]


def check_json_files(root=ROOT):
    """Return syntax errors in the plugin manifest and its schema."""
    errors = []
    for name in ("plugin.json", "plugin.schema.json"):
        print("Checking " + name, flush=True)
        try:
            with (Path(root) / name).open("r", encoding="utf-8") as handle:
                json.load(handle)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append("{}: {}".format(name, exc))
    return errors


def main():
    errors = check_json_files()
    if errors:
        for error in errors:
            print("Invalid JSON: " + error, flush=True)
        return 1

    compile_command = [sys.executable, "-m", "compileall", "-q", "travel_shared", "scripts"]
    print("Running " + " ".join(compile_command[1:]), flush=True)
    if subprocess.run(compile_command, cwd=ROOT).returncode != 0:
        return 1

    commands = [[sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]]
    commands += [[sys.executable, str(path)] for path in sorted(ROOT.glob("skills/*/scripts/test_*.py"))]
    commands.append([sys.executable, "rag/scripts/validate_skill_manifest.py"])
    failed = 0
    # Keep tests away from a real user database and use one encoding on Windows.
    with TemporaryDirectory(prefix="travel-checks-") as temp_dir:
        env = os.environ.copy()
        test_db = str(Path(temp_dir) / "internal.sqlite3")
        env["TRAVEL_INTERNAL_DB"] = test_db
        env["TRAVEL_PREFERENCES_DB"] = test_db
        env["PYTHONUTF8"] = "1"
        for command in commands:
            print("Running " + " ".join(command[1:]), flush=True)
            failed += subprocess.run(command, cwd=ROOT, env=env).returncode != 0
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
