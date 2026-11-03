"""Resolve one exact cached model revision for indexing and retrieval."""

import re
from pathlib import Path


REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def _repo_id(model_name):
    return model_name if "/" in model_name else "sentence-transformers/" + model_name


def load_model(model_name, revision=None, allow_download=False):
    """Return (model, commit SHA); retrieval never silently switches revisions."""
    from huggingface_hub import snapshot_download
    from sentence_transformers import SentenceTransformer

    if revision is not None and not REVISION_PATTERN.fullmatch(revision):
        raise ValueError("embedding model revision must be a 40-character commit SHA")
    repo_id = _repo_id(model_name)
    try:
        snapshot = snapshot_download(repo_id, revision=revision, local_files_only=True)
        model = SentenceTransformer(snapshot, local_files_only=True)
    except Exception as cached_error:
        if not allow_download:
            raise RuntimeError(
                "embedding model revision is unavailable in the local cache; "
                "cache the exact revision before retrieval"
            ) from cached_error
        snapshot = snapshot_download(repo_id, revision=revision, local_files_only=False)
        model = SentenceTransformer(snapshot, local_files_only=True)
    resolved = Path(snapshot).name
    if not REVISION_PATTERN.fullmatch(resolved):
        raise RuntimeError("could not resolve the embedding model to a pinned commit")
    if revision is not None and resolved != revision:
        raise RuntimeError("cached model revision differs from the index")
    return model, resolved
