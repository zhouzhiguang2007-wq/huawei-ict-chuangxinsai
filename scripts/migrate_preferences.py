"""把旧偏好库迁移到内部私有库（合库后的数据搬家）。

背景：默认存储已从 `~/.travel-planner/preferences.sqlite3` 改为
`~/.travel-planner/internal.sqlite3`，旧文件里的偏好不会自动出现。
本脚本做一次性迁移，支持 dry-run、自动备份与「保留更新时间较新者」。

用法：
    python scripts/migrate_preferences.py
    python scripts/migrate_preferences.py --from old.sqlite3 --to new.sqlite3
    python scripts/migrate_preferences.py --dry-run

退出码：0 完成/无需迁移；1 出错。纯标准库。
"""

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from travel_shared.db import default_internal_db_path, get_connection

DEFAULT_SOURCE = Path.home() / ".travel-planner" / "preferences.sqlite3"

_COLUMNS = ("user_id", "field", "value_json", "source", "updated_at")


def _load_rows(source):
    conn = sqlite3.connect(str(source))
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='preferences'"
        ).fetchone()
        if not exists:
            return []
        return conn.execute(
            "SELECT user_id, field, value_json, source, updated_at "
            "FROM preferences"
        ).fetchall()
    finally:
        conn.close()


def migrate(source, target, *, dry_run=False, backup=True):
    """把 source 的偏好合并进 target，返回统计报告。"""
    source = Path(source)
    target = Path(target)
    report = {
        "source": str(source),
        "target": str(target),
        "source_rows": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "backup": None,
        "status": "ok",
    }

    if not source.is_file():
        report["status"] = "skipped_no_source"
        return report

    rows = _load_rows(source)
    report["source_rows"] = len(rows)
    if not rows:
        report["status"] = "skipped_empty_source"
        return report
    if dry_run:
        report["status"] = "dry_run"
        return report

    if backup and target.exists():
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = target.with_name(target.name + ".bak." + stamp)
        shutil.copy2(str(target), str(backup_path))
        report["backup"] = str(backup_path)

    conn = get_connection(str(target))
    try:
        with conn:
            for user_id, field, value_json, source_text, updated_at in rows:
                existing = conn.execute(
                    "SELECT updated_at FROM preferences WHERE user_id=? AND field=?",
                    (user_id, field),
                ).fetchone()
                if existing and (existing[0] or "") >= (updated_at or ""):
                    report["skipped"] += 1
                    continue
                conn.execute(
                    "INSERT INTO preferences "
                    "(user_id, field, value_json, source, updated_at) "
                    "VALUES (?,?,?,?,?) "
                    "ON CONFLICT(user_id, field) DO UPDATE SET "
                    "value_json=excluded.value_json, source=excluded.source, "
                    "updated_at=excluded.updated_at",
                    (user_id, field, value_json, source_text, updated_at),
                )
                if existing:
                    report["updated"] += 1
                else:
                    report["inserted"] += 1
    finally:
        conn.close()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="把旧 preferences.sqlite3 的偏好迁移到内部私有库")
    parser.add_argument("--from", dest="source", default=str(DEFAULT_SOURCE),
                        help="旧偏好库路径")
    parser.add_argument("--to", dest="target", default=None,
                        help="目标内部库路径（默认读 TRAVEL_INTERNAL_DB）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只统计，不写入、不备份")
    parser.add_argument("--no-backup", dest="backup", action="store_false",
                        help="跳过目标文件备份")
    args = parser.parse_args(argv)

    target = args.target or str(default_internal_db_path())
    report = migrate(args.source, target, dry_run=args.dry_run,
                     backup=args.backup)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())