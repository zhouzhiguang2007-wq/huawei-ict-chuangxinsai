"""Build a source-tracked local RAG index from all Skills and workflow docs."""

import argparse
import json
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from chunk_strategy import load_and_split
from index_state import INDEX_SCHEMA_VERSION, digest_file, source_snapshot
from model_loader import load_model


RAG_DIR = Path(__file__).resolve().parent


def load_config():
    import yaml

    with (RAG_DIR / "config.yaml").open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true",
                        help="require an already cached embedding model")
    args = parser.parse_args()

    cfg = load_config()
    corpus = (RAG_DIR.parent / cfg.get("corpus_dir", "skills")).resolve()
    index_dir = (RAG_DIR / cfg.get("index_dir", "index")).resolve()
    config_path = RAG_DIR / "config.yaml"
    snapshot_before = source_snapshot(corpus, config_path)
    chunks = load_and_split(corpus, max_chars=int(cfg.get("max_chars", 800)))
    if not chunks:
        parser.error("no Skill or workflow chunks found; check corpus_dir")

    model, revision = load_model(cfg["embedding_model"], allow_download=not args.offline)
    vectors = np.asarray(model.encode([chunk.text for chunk in chunks],
                                      normalize_embeddings=True, show_progress_bar=True),
                         dtype=np.float32)
    if vectors.ndim != 2 or vectors.shape[0] != len(chunks):
        raise RuntimeError("embedding count does not match source chunks")
    snapshot_after = source_snapshot(corpus, config_path)
    if snapshot_before != snapshot_after:
        raise RuntimeError("Skill or workflow text changed during indexing; retry after edits finish")

    index_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rag-build-", dir=index_dir.parent) as temp_name:
        staging = Path(temp_name)
        vectors_path = staging / "vectors.npy"
        chunks_path = staging / "chunks.jsonl"
        np.save(vectors_path, vectors)
        with chunks_path.open("w", encoding="utf-8", newline="\n") as stream:
            for chunk in chunks:
                stream.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")
        meta = {
            "index_schema_version": INDEX_SCHEMA_VERSION,
            "embedding_model": cfg["embedding_model"],
            "model_revision": revision,
            "dim": int(vectors.shape[1]),
            "n": len(chunks),
            "build_time": datetime.now(timezone.utc).isoformat(),
            **snapshot_after,
            "artifacts": {"vectors.npy": digest_file(vectors_path),
                          "chunks.jsonl": digest_file(chunks_path)},
        }
        meta_path = staging / "meta.json"
        with meta_path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
        # Metadata is installed last; readers reject any mixed old/new artifacts.
        os.replace(vectors_path, index_dir / "vectors.npy")
        os.replace(chunks_path, index_dir / "chunks.jsonl")
        os.replace(meta_path, index_dir / "meta.json")

    print("indexed %d chunks from %d sources, dim=%d -> %s" %
          (meta["n"], len(meta["sources"]), meta["dim"], index_dir))


if __name__ == "__main__":
    main()
