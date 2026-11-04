"""Index provenance and freshness checks using only the Python standard library."""

import hashlib
import json
import re
import sys
from pathlib import Path

try:
    from .chunk_strategy import normalized_text, source_files
except ImportError:  # python rag/index_state.py or python rag/retrieve.py
    from chunk_strategy import normalized_text, source_files


INDEX_SCHEMA_VERSION = 2
ARTIFACTS = ("chunks.jsonl", "vectors.npy")


def digest_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest_file(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def source_snapshot(corpus_root, config_path):
    """Hash normalized text so checkout line endings do not invalidate the index."""
    sources = {relative: digest_text(normalized_text(path))
               for relative, _, path in source_files(corpus_root)}
    config_digest = digest_text(normalized_text(config_path))
    identity = json.dumps({"sources": sources, "config_sha256": config_digest},
                          sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return {"sources": sources, "config_sha256": config_digest,
            "corpus_sha256": digest_text(identity)}


def check_index(index_dir, corpus_root, config_path):
    """Return a machine-readable status without loading NumPy or the model."""
    index_dir = Path(index_dir)
    meta_path = index_dir / "meta.json"
    if not meta_path.is_file():
        return {"status": "missing", "reasons": ["rag/index/meta.json is missing"]}
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            raise ValueError("meta.json must be an object")
    except (OSError, ValueError) as exc:
        return {"status": "invalid", "reasons": ["cannot read meta.json: " + str(exc)]}
    try:
        snapshot = source_snapshot(corpus_root, config_path)
    except (OSError, UnicodeError, ValueError) as exc:
        return {"status": "invalid", "reasons": ["cannot read current sources: " + str(exc)]}

    reasons = []
    if meta.get("index_schema_version") != INDEX_SCHEMA_VERSION:
        reasons.append("index schema is old; rebuild the index")
    if not isinstance(meta.get("model_revision"), str) or not re.fullmatch(
            r"[0-9a-f]{40}", meta["model_revision"]):
        reasons.append("embedding model revision is missing or invalid")
    old_sources = meta.get("sources")
    if not isinstance(old_sources, dict):
        reasons.append("source manifest is missing")
        old_sources = {}
    current_sources = snapshot["sources"]
    for path in sorted(current_sources.keys() - old_sources.keys()):
        reasons.append("source added: " + path)
    for path in sorted(old_sources.keys() - current_sources.keys()):
        reasons.append("source removed: " + path)
    for path in sorted(current_sources.keys() & old_sources.keys()):
        if current_sources[path] != old_sources[path]:
            reasons.append("source changed: " + path)
    if meta.get("config_sha256") != snapshot["config_sha256"]:
        reasons.append("rag/config.yaml changed")
    if meta.get("corpus_sha256") != snapshot["corpus_sha256"] and not reasons:
        reasons.append("corpus digest differs")

    artifacts = meta.get("artifacts")
    if not isinstance(artifacts, dict):
        reasons.append("artifact hashes are missing")
        artifacts = {}
    for name in ARTIFACTS:
        path = index_dir / name
        if not path.is_file():
            reasons.append("index artifact missing: " + name)
        elif artifacts.get(name) != digest_file(path):
            reasons.append("index artifact changed: " + name)
    if not reasons:
        chunks_path = index_dir / "chunks.jsonl"
        try:
            with chunks_path.open(encoding="utf-8") as stream:
                chunk_count = sum(bool(line.strip()) for line in stream)
            if chunk_count != meta.get("n"):
                reasons.append("chunk count differs from metadata")
        except (OSError, UnicodeError) as exc:
            reasons.append("cannot count chunks: " + str(exc))

    return {"status": "fresh" if not reasons else "stale",
            "reasons": reasons, "indexed_sources": len(old_sources),
            "current_sources": len(current_sources), "chunks": meta.get("n"),
            "build_time": meta.get("build_time")}


def emit_json(value):
    """Emit UTF-8 JSON even when Windows starts Python with a GBK console."""
    payload = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        payload.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        payload = json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2)
    sys.stdout.write(payload + "\n")
