"""Deterministically collect and split current Skill and workflow manuals."""

import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Chunk:
    chunk_id: str
    skill: str
    file: str
    heading_path: str
    text: str


def source_files(corpus_root):
    """Yield (repository-relative path, skill, absolute path) in stable order."""
    corpus_root = Path(corpus_root).resolve()
    repository_root = corpus_root.parent
    files = []
    for skill_dir in sorted(corpus_root.iterdir()):
        if not skill_dir.is_dir():
            continue
        entry = skill_dir / "SKILL.md"
        if entry.is_file():
            files.append((entry.relative_to(repository_root).as_posix(), skill_dir.name, entry))
        references = skill_dir / "references"
        if references.is_dir():
            for path in sorted(references.rglob("*.md")):
                files.append((path.relative_to(repository_root).as_posix(), skill_dir.name, path))
    docs = repository_root / "docs"
    if docs.is_dir():
        for path in sorted(docs.rglob("*.md")):
            files.append((path.relative_to(repository_root).as_posix(), "shared", path))
    return sorted(files, key=lambda item: item[0])


def normalized_text(path):
    """Normalize line endings so a committed index stays valid on Windows/Linux."""
    return Path(path).read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def _bounded_parts(text, max_chars):
    """Split unusually long paragraphs without exceeding max_chars."""
    while len(text) > max_chars:
        cut = max(text.rfind("\n", 0, max_chars + 1),
                  text.rfind("。", 0, max_chars + 1),
                  text.rfind("；", 0, max_chars + 1),
                  text.rfind(" ", 0, max_chars + 1))
        if cut < max_chars // 2:
            cut = max_chars
        elif text[cut:cut + 1] in ("。", "；"):
            cut += 1
        yield text[:cut].strip()
        text = text[cut:].strip()
    if text:
        yield text


def split_markdown(text, max_chars=800):
    if not isinstance(max_chars, int) or isinstance(max_chars, bool) or max_chars < 100:
        raise ValueError("max_chars must be an integer >= 100")
    blocks = []
    current = []
    headings = []
    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.*)", line)
        if match:
            if current:
                blocks.append((" / ".join(title for _, title in headings), "\n".join(current)))
                current = []
            level = len(match.group(1))
            while headings and headings[-1][0] >= level:
                headings.pop()
            headings.append((level, match.group(2).strip()))
        current.append(line)
    if current:
        blocks.append((" / ".join(title for _, title in headings), "\n".join(current)))

    chunks = []
    for heading_path, body in blocks:
        paragraphs = re.split(r"\n\s*\n", body.strip())
        buffer = ""
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            for piece in _bounded_parts(paragraph, max_chars):
                candidate = (buffer + "\n\n" + piece).strip() if buffer else piece
                if len(candidate) > max_chars and buffer:
                    chunks.append((heading_path, buffer))
                    buffer = piece
                else:
                    buffer = candidate
        if buffer:
            chunks.append((heading_path, buffer))
    return chunks


def load_and_split(corpus_root, max_chars=800):
    chunks = []
    for relative_path, skill, path in source_files(corpus_root):
        for heading_path, body in split_markdown(normalized_text(path), max_chars=max_chars):
            if body:
                chunks.append(Chunk(f"c{len(chunks):05d}", skill, relative_path,
                                    heading_path, body))
    return chunks


if __name__ == "__main__":
    import json
    import sys

    corpus = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "skills"
    for chunk in load_and_split(corpus):
        print(json.dumps(asdict(chunk), ensure_ascii=True))
