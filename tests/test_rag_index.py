"""Offline checks for RAG source coverage, freshness and portable output."""

import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from rag.chunk_strategy import load_and_split, source_files, split_markdown
from rag.index_state import (INDEX_SCHEMA_VERSION, check_index, digest_file,
                             emit_json, source_snapshot)
from rag.model_loader import load_model


class RagIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skills = self.root / "skills"
        self.skill = self.skills / "planner"
        (self.skill / "references").mkdir(parents=True)
        (self.root / "docs").mkdir()
        (self.root / "rag").mkdir()
        self.index = self.root / "rag" / "index"
        self.index.mkdir()
        (self.skill / "SKILL.md").write_text("# Planner\n\n## Route\nUse times.\n", encoding="utf-8")
        (self.skill / "references" / "route.md").write_text(
            "# Route\n\n## Daily\nShow every transfer.\n", encoding="utf-8")
        (self.root / "docs" / "shared.md").write_text(
            "# Shared\nUse a common context.\n", encoding="utf-8")
        self.config = self.root / "rag" / "config.yaml"
        self.config.write_text("max_chars: 800\n", encoding="utf-8")

    def write_fake_index(self):
        snapshot = source_snapshot(self.skills, self.config)
        (self.index / "chunks.jsonl").write_text('{"chunk_id":"c00000"}\n', encoding="utf-8")
        (self.index / "vectors.npy").write_bytes(b"sample vector artifact")
        meta = {"index_schema_version": INDEX_SCHEMA_VERSION, "n": 1, "dim": 2,
                "model_revision": "a" * 40,
                **snapshot,
                "artifacts": {name: digest_file(self.index / name)
                              for name in ("chunks.jsonl", "vectors.npy")}}
        (self.index / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    def test_indexes_all_skill_entries_references_and_shared_docs(self):
        paths = {name for name, _, _ in source_files(self.skills)}
        self.assertEqual(paths, {"skills/planner/SKILL.md",
                                 "skills/planner/references/route.md", "docs/shared.md"})
        chunks = load_and_split(self.skills)
        self.assertEqual({chunk.file for chunk in chunks}, paths)
        self.assertIn("shared", {chunk.skill for chunk in chunks})

    def test_heading_levels_do_not_nest_sibling_h2_sections(self):
        chunks = split_markdown("## First\nA\n## Second\nB\n### Child\nC", max_chars=100)
        paths = [path for path, _ in chunks]
        self.assertEqual(paths, ["First", "Second", "Second / Child"])

    def test_long_paragraphs_stay_bounded(self):
        chunks = split_markdown("# Long\n" + "甲" * 263, max_chars=100)
        self.assertTrue(chunks)
        self.assertTrue(all(len(body) <= 100 for _, body in chunks))
        self.assertEqual("".join(body.replace("\n", "") for _, body in chunks),
                         "# Long" + "甲" * 263)

    def test_line_ending_changes_do_not_mark_index_stale(self):
        self.write_fake_index()
        original = self.skill / "SKILL.md"
        original.write_bytes(original.read_bytes().replace(b"\r\n", b"\n")
                             .replace(b"\n", b"\r\n"))
        self.assertEqual(check_index(self.index, self.skills, self.config)["status"], "fresh")

    def test_source_edit_marks_index_stale(self):
        self.write_fake_index()
        (self.skill / "SKILL.md").write_text("# Planner\nChanged.\n", encoding="utf-8")
        result = check_index(self.index, self.skills, self.config)
        self.assertEqual(result["status"], "stale")
        self.assertIn("source changed: skills/planner/SKILL.md", result["reasons"])

    def test_new_workflow_doc_marks_index_stale(self):
        self.write_fake_index()
        (self.root / "docs" / "new.md").write_text("# New\n", encoding="utf-8")
        result = check_index(self.index, self.skills, self.config)
        self.assertIn("source added: docs/new.md", result["reasons"])

    def test_config_or_vector_change_marks_index_stale(self):
        self.write_fake_index()
        self.config.write_text("max_chars: 400\n", encoding="utf-8")
        self.assertIn("rag/config.yaml changed",
                      check_index(self.index, self.skills, self.config)["reasons"])
        self.config.write_text("max_chars: 800\n", encoding="utf-8")
        (self.index / "vectors.npy").write_bytes(b"corrupted")
        self.assertIn("index artifact changed: vectors.npy",
                      check_index(self.index, self.skills, self.config)["reasons"])

    def test_old_index_without_manifest_is_stale(self):
        (self.index / "meta.json").write_text('{"n":1,"dim":2}', encoding="utf-8")
        self.assertEqual(check_index(self.index, self.skills, self.config)["status"], "stale")

    def test_gbk_console_gets_utf8_json(self):
        buffer = io.BytesIO()
        output = io.TextIOWrapper(buffer, encoding="gbk", write_through=True)
        with patch.object(sys, "stdout", output):
            emit_json({"text": "￥价格 ¥"})
        result = json.loads(buffer.getvalue().decode("utf-8"))
        self.assertEqual(result["text"], "￥价格 ¥")

    def test_cached_model_is_tried_before_network(self):
        calls = []

        def fake_snapshot(name, *, revision=None, local_files_only=False):
            calls.append((name, revision, local_files_only))
            if local_files_only:
                return "/cache/snapshots/" + "a" * 40
            raise AssertionError("unexpected network fallback")

        def fake_model(path, *, local_files_only=False):
            self.assertTrue(local_files_only)
            return "cached-model"

        with patch.dict(sys.modules, {
                "sentence_transformers": types.SimpleNamespace(SentenceTransformer=fake_model),
                "huggingface_hub": types.SimpleNamespace(snapshot_download=fake_snapshot)}):
            self.assertEqual(load_model("demo"), ("cached-model", "a" * 40))
        self.assertEqual(calls, [("sentence-transformers/demo", None, True)])

    def test_uncached_retrieval_fails_without_network(self):
        calls = []

        def fake_snapshot(name, *, revision=None, local_files_only=False):
            calls.append(local_files_only)
            raise OSError("cache miss")

        with patch.dict(sys.modules, {
                "sentence_transformers": types.SimpleNamespace(SentenceTransformer=lambda *a, **k: None),
                "huggingface_hub": types.SimpleNamespace(snapshot_download=fake_snapshot)}):
            with self.assertRaisesRegex(RuntimeError, "local cache"):
                load_model("demo", allow_download=False)
        self.assertEqual(calls, [True])

    def test_pinned_revision_must_match_resolved_snapshot(self):
        with patch.dict(sys.modules, {
                "sentence_transformers": types.SimpleNamespace(
                    SentenceTransformer=lambda *a, **k: "model"),
                "huggingface_hub": types.SimpleNamespace(
                    snapshot_download=lambda *a, **k: "/cache/snapshots/" + "a" * 40)}):
            with self.assertRaisesRegex(RuntimeError, "differs from the index"):
                load_model("demo", revision="b" * 40)


if __name__ == "__main__":
    unittest.main()
