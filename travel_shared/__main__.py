"""Local trusted operator entrypoint: python -m travel_shared --help."""

import argparse
import json
import sys
from pathlib import Path

from .tools import DEFAULT_DB, TravelTools


def main():
    # Tool output is UTF-8 JSON even when the Windows console defaults to GBK.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--user-id", required=True, help="trusted host identity, not model-generated")
    parser.add_argument("input", nargs="?", help="JSON request file; omitted reads stdin")
    args = parser.parse_args()
    try:
        request = json.loads(Path(args.input).read_text(encoding="utf-8-sig") if args.input else sys.stdin.read())
    except (OSError, ValueError) as exc:
        result = TravelTools._result(None, "invalid", errors=[str(exc)])
    else:
        result = TravelTools(args.db).handle(request, user_id=args.user_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return {"ok": 0, "invalid": 2, "unavailable": 3}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
