"""Markdown corpus ingestion."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from quiver.project import append_event, content_hash, now_iso, read_config, read_json, require_project, slugify, write_json


PAPER_METADATA_FIELDS = {
    "mrnumber",
    "title",
    "authors",
    "doi",
    "doi_url",
    "journal",
    "year",
    "volume",
    "number",
    "pages",
    "page_count_estimate",
    "primary_msc",
    "primary_msc_description",
    "citation_count",
    "item_type",
    "entry_type",
    "selection_tags",
    "topic_selection",
}


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


def _load_metadata_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = __import__("json").loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _load_paper_metadata(root: Path) -> dict[str, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    jsonl_path = root / "sources" / "paper_metadata.jsonl"
    json_path = root / "sources" / "paper_metadata.json"
    rows.extend(_load_metadata_jsonl(jsonl_path))
    payload = read_json(json_path, default=None)
    if isinstance(payload, list):
        rows.extend(item for item in payload if isinstance(item, dict))
    elif isinstance(payload, dict):
        source = payload.get("papers") or payload.get("items")
        if isinstance(source, list):
            rows.extend(item for item in source if isinstance(item, dict))

    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        raw_id = row.get("id") or row.get("paper_id")
        if not raw_id:
            continue
        paper_id = slugify(str(raw_id), limit=80)
        metadata = {key: row[key] for key in PAPER_METADATA_FIELDS if key in row}
        metadata["id"] = paper_id
        by_id[paper_id] = metadata
    return by_id


def scan_papers(root: Path) -> dict[str, Any]:
    root = require_project(root)
    config = read_config(root)
    pattern = config.get("paper_glob", "sources/papers/**/*.md")
    metadata_by_id = _load_paper_metadata(root)
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
        metadata = metadata_by_id.get(base_id, {})
        words = re.findall(r"\w+", text)
        paper = {
            "id": paper_id,
            "title": metadata.get("title") or _title_from_markdown(text, path.stem),
            "path": rel,
            "sha256": content_hash(text),
            "word_count": len(words),
        }
        for key, value in metadata.items():
            if key not in {"id", "title"}:
                paper[key] = value
        papers.append(paper)

    payload = {
        "schema_version": "quiver.paper_index.v1",
        "generated_at": now_iso(),
        "papers": papers,
    }
    write_json(root / ".quiver" / "artifacts" / "paper_index.json", payload)
    append_event(root, "papers.ingest", {"count": len(papers)})
    return payload
