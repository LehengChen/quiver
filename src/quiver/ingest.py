"""Markdown corpus ingestion."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from quiver.project import append_event, content_hash, now_iso, read_config, require_project, slugify, write_json


def _is_image_only_line(text: str) -> bool:
    return bool(re.fullmatch(r"!\[[^\]]*\]\([^)]+\)", text.strip()))


def _title_from_markdown(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if not heading or _is_image_only_line(heading):
                continue
            return heading
        if _is_image_only_line(stripped):
            continue
        return stripped[:120]
    return fallback


def _paper_id(path: Path) -> str:
    return slugify(path.stem, limit=80)


def scan_papers(root: Path) -> dict[str, Any]:
    root = require_project(root)
    config = read_config(root)
    pattern = config.get("paper_glob", "sources/papers/**/*.md")
    papers: list[dict[str, Any]] = []
    seen: set[str] = set()

    for path in sorted(root.glob(pattern)):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        base_id = _paper_id(path)
        paper_id = base_id
        if paper_id in seen:
            paper_id = slugify(f"{base_id}-{content_hash(rel)[:8]}", limit=90)
        seen.add(paper_id)
        words = re.findall(r"\w+", text)
        papers.append(
            {
                "id": paper_id,
                "title": _title_from_markdown(text, path.stem),
                "path": rel,
                "sha256": content_hash(text),
                "word_count": len(words),
            }
        )

    payload = {
        "schema_version": "quiver.paper_index.v1",
        "generated_at": now_iso(),
        "papers": papers,
    }
    write_json(root / ".quiver" / "artifacts" / "paper_index.json", payload)
    append_event(root, "papers.ingest", {"count": len(papers)})
    return payload
