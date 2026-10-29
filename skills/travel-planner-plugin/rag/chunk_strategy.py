import os
import re
import json
import glob
from dataclasses import dataclass, asdict


@dataclass
class Chunk:
    chunk_id: str
    skill: str
    file: str
    heading_path: str
    text: str


def split_markdown(text, max_chars=800):
    lines = text.split("\n")
    blocks = []
    current = []
    current_heading = []
    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            if current:
                blocks.append((" / ".join(current_heading), "\n".join(current)))
                current = []
            level = len(m.group(1))
            title = m.group(2).strip()
            while len(current_heading) >= level:
                current_heading.pop()
            current_heading.append(title)
        current.append(line)
    if current:
        blocks.append((" / ".join(current_heading), "\n".join(current)))
    chunks = []
    for heading_path, body in blocks:
        if len(body) > max_chars:
            paras = re.split(r"\n\s*\n", body)
            buf = ""
            for p in paras:
                if len(buf) + len(p) > max_chars and buf:
                    chunks.append((heading_path, buf.strip()))
                    buf = p + "\n\n"
                else:
                    buf += p + "\n\n"
            if buf.strip():
                chunks.append((heading_path, buf.strip()))
        else:
            chunks.append((heading_path, body.strip()))
    return chunks


def load_and_split(corpus_root):
    all_chunks = []
    skill_dirs = glob.glob(os.path.join(corpus_root, "*"))
    cid = 0
    for sd in sorted(skill_dirs):
        if not os.path.isdir(sd):
            continue
        skill = os.path.basename(sd)
        refs_dir = os.path.join(sd, "references")
        if not os.path.isdir(refs_dir):
            continue
        for fpath in sorted(glob.glob(os.path.join(refs_dir, "**", "*.md"), recursive=True)):
            with open(fpath, "r", encoding="utf-8") as f:
                text = f.read()
            for heading_path, body in split_markdown(text):
                if not body.strip():
                    continue
                all_chunks.append(Chunk(
                    f"c{cid:05d}",
                    skill,
                    os.path.relpath(fpath, corpus_root),
                    heading_path,
                    body.strip(),
                ))
                cid += 1
    return all_chunks


if __name__ == "__main__":
    import sys
    corpus = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "skills")
    chunks = load_and_split(corpus)
    for c in chunks:
        print(json.dumps(asdict(c), ensure_ascii=False))