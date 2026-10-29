import os
import sys
import json
import argparse
import numpy as np


def load_config():
    import yaml
    cfg_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    ap = argparse.ArgumentParser(description="本地 RAG 检索")
    ap.add_argument("query", help="检索查询")
    ap.add_argument("--top-k", type=int, default=None)
    ap.add_argument("--skill", default=None, help="只在该 skill 语料内检索")
    ap.add_argument("--index-dir", default=None)
    args = ap.parse_args()

    cfg = load_config()
    here = os.path.dirname(__file__)
    index_dir = args.index_dir or os.path.join(here, cfg.get("index_dir", "index"))
    top_k = args.top_k or cfg.get("top_k", 5)

    vectors_path = os.path.join(index_dir, "vectors.npy")
    chunks_path = os.path.join(index_dir, "chunks.jsonl")
    if not os.path.exists(vectors_path) or not os.path.exists(chunks_path):
        print(json.dumps({"error": "index not found, run build_index.py first", "index_dir": index_dir}, ensure_ascii=False))
        sys.exit(1)

    vectors = np.load(vectors_path)
    chunks = []
    with open(chunks_path, "r", encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(cfg["embedding_model"])
    qv = model.encode([args.query], normalize_embeddings=True)
    qv = np.asarray(qv, dtype=np.float32)
    scores = (qv @ vectors.T)[0]
    order = np.argsort(scores)[::-1]

    results = []
    for i in order:
        c = chunks[i]
        if args.skill and c["skill"] != args.skill:
            continue
        results.append({**c, "score": float(scores[i])})
        if len(results) >= top_k:
            break

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()