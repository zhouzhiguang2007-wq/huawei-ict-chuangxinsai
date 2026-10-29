import os
import sys
import glob
import re
import json

ALLOWED = {"name", "description", "language", "allowed-tools"}


def parse_frontmatter(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if not text.startswith("---"):
        return None, "no frontmatter"
    end = text.find("\n---", 3)
    if end < 0:
        return None, "no frontmatter end"
    fm = text[3:end]
    keys = set()
    for line in fm.splitlines():
        m = re.match(r"^([A-Za-z0-9_-]+):", line)
        if m:
            keys.add(m.group(1))
    return keys, None


def main():
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    skills_dir = os.path.join(here, "skills")
    errors = []
    ok = 0
    for skill_md in sorted(glob.glob(os.path.join(skills_dir, "*", "SKILL.md"))):
        keys, err = parse_frontmatter(skill_md)
        if err:
            errors.append(f"{skill_md}: {err}")
            continue
        extra = keys - ALLOWED
        if "name" not in keys or "description" not in keys:
            errors.append(f"{skill_md}: missing name/description")
        elif extra:
            errors.append(f"{skill_md}: extra fields {sorted(extra)}")
        else:
            ok += 1
    print(json.dumps({"ok": ok, "errors": errors}, ensure_ascii=False, indent=2))
    sys.exit(0 if not errors else 1)


if __name__ == "__main__":
    main()