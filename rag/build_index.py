import os
import sys
import json
import time
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from chunk_strategy import load_and_split
from dataclasses import asdict


def load_config():
    import yaml
    cfg_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    cfg = load_config()
    here = os.path.dirname(__file__)
    corpus = os.path.join(here, "..", cfg.get("corpus_dir", "skills"))
    index_dir = os.path.join(here, cfg.get("index_dir", "index"))
    os.makedirs(index_dir, exist_ok=True)

    chunks = load_and_split(corpus)
    if not chunks:
        print("no chunks; check corpus_dir", file=sys.stderr)
        sys.exit(1)

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(cfg["embedding_model"])
    texts = [c.text for c in chunks]
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    vectors = np.asarray(vectors, dtype=np.float32)

    np.save(os.path.join(index_dir, "vectors.npy"), vectors)
    with open(os.path.join(index_dir, "chunks.jsonl"), "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")

    meta = {
        "embedding_model": cfg["embedding_model"],
        "dim": int(vectors.shape[1]),
        "n": int(vectors.shape[0]),
        "build_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(index_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"indexed {meta['n']} chunks, dim={meta['dim']} -> {index_dir}")


if __name__ == "__main__":
    main()