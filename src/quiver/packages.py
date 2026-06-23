"""Build Codex-ready paper packages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quiver.concept_quality import concept_node_exclusion_reason
from quiver.project import append_event, now_iso, read_config, read_json, require_project, write_json
from quiver.search import search_local


def _excerpt(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = text[: limit // 2].rstrip()
    tail = text[-limit // 2 :].lstrip()
    return head + "\n\n[... middle omitted by quiver package builder ...]\n\n" + tail


def _allowed_existing_nodes(graph: dict[str, Any], search_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result_ids = {item.get("id") for item in search_results if item.get("kind") == "graph_node"}
    by_id = {node.get("id"): node for node in graph.get("nodes", []) or [] if node.get("id")}
    edges = graph.get("edges", []) or []
    allowed: list[dict[str, Any]] = []
    for node_id in sorted(result_ids):
        node = by_id.get(node_id)
        if not node:
            continue
        if concept_node_exclusion_reason(node):
            continue
        allowed.append(
            {
                "id": node_id,
                "label": node.get("label"),
                "entity_type": node.get("entity_type"),
                "local_role": node.get("local_role"),
                "summary": node.get("summary"),
                "aliases": node.get("aliases", []) or [],
                "prerequisites": sorted(edge["prerequisite"] for edge in edges if edge.get("dependent") == node_id),
                "dependents": sorted(edge["dependent"] for edge in edges if edge.get("prerequisite") == node_id),
            }
        )
    return allowed


def build_packages(root: Path, *, paper_ids: list[str] | None = None, refresh: bool = False) -> dict[str, Any]:
    root = require_project(root)
    config = read_config(root)
    max_chars = int(config.get("max_excerpt_chars", 12000))
    max_search = int(config.get("max_search_results", 12))
    index = read_json(root / ".quiver" / "artifacts" / "paper_index.json", default={}) or {}
    wanted = set(paper_ids or [])
    packages: list[dict[str, Any]] = []

    for paper in index.get("papers", []) or []:
        if wanted and paper["id"] not in wanted:
            continue
        out_path = root / "work" / "packages" / f"{paper['id']}.json"
        if out_path.exists() and not refresh:
            packages.append({"paper_id": paper["id"], "path": out_path.relative_to(root).as_posix(), "status": "existing"})
            continue

        source_path = root / paper["path"]
        text = source_path.read_text(encoding="utf-8", errors="replace")
        source_excerpt = _excerpt(text, max_chars)
        search_query = f"{paper['title']}\n\n{source_excerpt}"
        search_results = search_local(root, search_query, limit=max_search)
        graph = read_json(root / "results" / "normalized" / "concept_graph.json", default={}) or {}
        payload = {
            "schema_version": "quiver.paper_package.v1",
            "generated_at": now_iso(),
            "paper": paper,
            "source_excerpt": source_excerpt,
            "existing_graph_summary": {
                "nodes": len(graph.get("nodes", []) or []),
                "edges": len(graph.get("edges", []) or []),
            },
            "local_search_results": search_results,
            "allowed_existing_nodes": _allowed_existing_nodes(graph, search_results),
            "extraction_policy": config.get("extraction_policy", {}),
            "output_schema": "quiver.graph_delta.v1",
        }
        write_json(out_path, payload)
        packages.append({"paper_id": paper["id"], "path": out_path.relative_to(root).as_posix(), "status": "written"})

    worklist = {
        "schema_version": "quiver.worklist.v1",
        "generated_at": now_iso(),
        "packages": packages,
    }
    write_json(root / "work" / "packages" / "worklist.json", worklist)
    append_event(root, "packages.build", {"count": len(packages), "refresh": refresh})
    return worklist
