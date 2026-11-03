"""Check that the committed RAG index matches current Skill and workflow text."""

import argparse
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG_DIR))
from index_state import check_index, emit_json  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-dir", type=Path, default=RAG_DIR / "index")
    parser.add_argument("--corpus-dir", type=Path, default=RAG_DIR.parent / "skills")
    parser.add_argument("--config", type=Path, default=RAG_DIR / "config.yaml")
    args = parser.parse_args()
    result = check_index(args.index_dir, args.corpus_dir, args.config)
    emit_json(result)
    return 0 if result["status"] == "fresh" else 1


if __name__ == "__main__":
    raise SystemExit(main())
