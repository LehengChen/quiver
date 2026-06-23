"""Project layout, atomic IO, and durable state helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quiver.schema_defs import GRAPH_DELTA_SCHEMA

MARKER = "quiver.toml"

PROJECT_DIRS = [
    "sources/papers",
    "references",
    "registry",
    "work/packages",
    "work/attempts",
    "work/claims",
    "results/deltas",
    "results/normalized",
    "results/projections",
    "results/site",
    "results/site-data",
    ".quiver/artifacts",
    ".quiver/logs",
    ".quiver/runs",
    ".quiver/schemas",
    "memory/attempts",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def slugify(text: str, limit: int = 80) -> str:
    out = re.sub(r"[^A-Za-z0-9._-]+", "-", text.strip().lower())
    out = re.sub(r"-+", "-", out).strip("-._")
    return (out or "item")[:limit]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def resolve_project(path: str | Path) -> Path:
    return Path(path).resolve()


def is_project(path: str | Path) -> bool:
    return (resolve_project(path) / MARKER).exists()


def find_project_root(path: str | Path) -> Path | None:
    cur = resolve_project(path)
    for candidate in [cur, *cur.parents]:
        if (candidate / MARKER).exists():
            return candidate
    return None


def require_project(path: str | Path) -> Path:
    root = find_project_root(path)
    if root is None:
        raise FileNotFoundError(f"not a Quiver project (no {MARKER}): {resolve_project(path)}")
    return root


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def _write_if_missing(path: Path, text: str) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def read_project_metadata(root: Path) -> dict[str, str]:
    marker = root / MARKER
    text = marker.read_text(encoding="utf-8", errors="replace") if marker.exists() else ""

    def field(name: str, fallback: str) -> str:
        match = re.search(rf"^{re.escape(name)}\s*=\s*\"([^\"]*)\"", text, re.MULTILINE)
        return match.group(1) if match else fallback

    return {
        "id": field("id", project_id_from_path(root)),
        "title": field("title", root.name),
        "created_at": field("created_at", ""),
    }


def project_id_from_path(path: Path) -> str:
    return slugify(path.name, limit=60)


def empty_graph(project_id: str, title: str) -> dict[str, Any]:
    ts = now_iso()
    return {
        "schema_version": "quiver.graph.v1",
        "dataset": {
            "id": project_id,
            "title": title,
            "created_at": ts,
            "updated_at": ts,
        },
        "papers": [],
        "nodes": [],
        "edges": [],
    }


def init_project(root: Path, *, force: bool = False) -> dict[str, Any]:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    for rel in PROJECT_DIRS:
        (root / rel).mkdir(parents=True, exist_ok=True)

    project_id = project_id_from_path(root)
    created_at = now_iso()

    marker = root / MARKER
    if force or not marker.exists():
        marker.write_text(
            "[project]\n"
            f'id = "{project_id}"\n'
            f'title = "{root.name}"\n'
            f'created_at = "{created_at}"\n',
            encoding="utf-8",
        )

    config_path = root / ".quiver" / "config.json"
    if force or not config_path.exists():
        write_json(
            config_path,
            {
                "schema_version": "quiver.config.v1",
                "executor": "codex",
                "model": "",
                "paper_glob": "sources/papers/**/*.md",
                "max_excerpt_chars": 12000,
                "max_search_results": 12,
                "extraction_policy": {
                    "skip_existing_adequate_nodes": True,
                    "max_extension_depth": 1,
                    "prefer_local_search": True,
                },
                "codex": {
                    "command": "codex",
                    "args": ["exec", "--json"],
                    "sandbox": "read-only",
                    "timeout_seconds": 1200,
                },
            },
        )

    _write_if_missing(root / "STATUS.md", "# Quiver Status\n\nNo run has been executed yet.\n")
    _write_if_missing(root / "memory" / "DECISIONS.md", "# Decisions\n\n")
    _write_if_missing(root / "memory" / "BLOCKERS.jsonl", "")
    _write_if_missing(root / ".quiver" / "logs" / "events.jsonl", "")

    if force or not (root / "registry" / "entity_pool.json").exists():
        write_json(root / "registry" / "entity_pool.json", {"schema_version": "quiver.entity_pool.v1", "entities": []})
    if force or not (root / "registry" / "anchor_priors.json").exists():
        write_json(root / "registry" / "anchor_priors.json", {"schema_version": "quiver.anchor_priors.v1", "anchors": []})
    if force or not (root / "registry" / "false_friends.json").exists():
        write_json(root / "registry" / "false_friends.json", {"schema_version": "quiver.false_friends.v1", "items": []})
    if force or not (root / "results" / "normalized" / "concept_graph.json").exists():
        write_json(root / "results" / "normalized" / "concept_graph.json", empty_graph(project_id, root.name))
    if force or not (root / ".quiver" / "schemas" / "graph-delta.schema.json").exists():
        write_json(root / ".quiver" / "schemas" / "graph-delta.schema.json", GRAPH_DELTA_SCHEMA)

    append_event(root, "project.init", {"project_id": project_id, "force": force})
    return {"root": str(root), "project_id": project_id, "created": True}


def read_config(root: Path) -> dict[str, Any]:
    return read_json(root / ".quiver" / "config.json", default={}) or {}


def append_event(root: Path, event: str, payload: dict[str, Any] | None = None) -> None:
    append_jsonl(
        root / ".quiver" / "logs" / "events.jsonl",
        {"ts": now_iso(), "event": event, "payload": payload or {}},
    )


def status(root: Path) -> dict[str, Any]:
    root = require_project(root)
    paper_index = read_json(root / ".quiver" / "artifacts" / "paper_index.json", default={}) or {}
    graph = read_json(root / "results" / "normalized" / "concept_graph.json", default={}) or {}
    packages = sorted((root / "work" / "packages").glob("*.json"))
    deltas = sorted((root / "results" / "deltas").glob("*.json"))
    return {
        "root": str(root),
        "papers": len(paper_index.get("papers", [])),
        "packages": len([p for p in packages if p.name != "worklist.json"]),
        "deltas": len(deltas),
        "nodes": len(graph.get("nodes", [])),
        "edges": len(graph.get("edges", [])),
        "events": len(read_jsonl(root / ".quiver" / "logs" / "events.jsonl")),
    }
