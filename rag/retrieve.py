"""Retrieve current Skill guidance from the source-tracked local RAG index."""

import argparse
import json
from pathlib import Path

from index_state import check_index, emit_json
from model_loader import load_model


RAG_DIR = Path(__file__).resolve().parent


def load_config():
    import yaml

    with (RAG_DIR / "config.yaml").open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", help="检索查询")
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--skill", default=None, help="指定 Skill，仍包含共享工作流规范")
    parser.add_argument("--index-dir", type=Path, default=None)
    parser.add_argument("--check", action="store_true", help="只检查索引新鲜度，不加载模型")
    args = parser.parse_args()

    cfg = load_config()
    index_dir = args.index_dir or RAG_DIR / cfg.get("index_dir", "index")
    corpus_dir = RAG_DIR.parent / cfg.get("corpus_dir", "skills")
    state = check_index(index_dir, corpus_dir, RAG_DIR / "config.yaml")
    if state["status"] != "fresh":
        emit_json({"status": state["status"], "error": "RAG index is unavailable or stale; rebuild it",
                   "reasons": state["reasons"]})
        return 2
    if args.check:
        emit_json(state)
        return 0
    if not args.query:
        parser.error("query is required unless --check is used")
    top_k = args.top_k if args.top_k is not None else cfg.get("top_k", 5)
    if not isinstance(top_k, int) or top_k < 1:
        parser.error("--top-k must be a positive integer")

    import numpy as np

    vectors = np.load(Path(index_dir) / "vectors.npy", allow_pickle=False)
    with (Path(index_dir) / "chunks.jsonl").open(encoding="utf-8") as stream:
        chunks = [json.loads(line) for line in stream if line.strip()]
    if vectors.ndim != 2 or len(chunks) != vectors.shape[0]:
        emit_json({"status": "invalid", "error": "RAG vector/chunk dimensions disagree"})
        return 2

    try:
        meta = json.loads((Path(index_dir) / "meta.json").read_text(encoding="utf-8"))
        model, _ = load_model(cfg["embedding_model"], revision=meta["model_revision"],
                              allow_download=False)
    except RuntimeError as exc:
        emit_json({"status": "unavailable", "error": str(exc)})
        return 3
    query_vector = np.asarray(model.encode([args.query], normalize_embeddings=True),
                              dtype=np.float32)
    if query_vector.shape != (1, vectors.shape[1]):
        emit_json({"status": "invalid", "error": "embedding dimension differs from index"})
        return 2
    scores = (query_vector @ vectors.T)[0]
    results = []
    for index in np.argsort(scores)[::-1]:
        chunk = chunks[int(index)]
        if args.skill and chunk["skill"] not in (args.skill, "shared"):
            continue
        results.append({**chunk, "score": float(scores[index])})
        if len(results) >= top_k:
            break
    emit_json(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
