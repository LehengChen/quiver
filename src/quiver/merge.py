"""Deterministic graph-delta merge."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quiver.project import append_event, now_iso, read_json, read_project_metadata, require_project, write_json
from quiver.validate import validate_delta


PUBLIC_PAPER_FIELDS = {
    "id",
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


def _merge_unique(old: list[Any], new: list[Any]) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for item in [*old, *new]:
        key = str(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


ADEQUACY_ORDER = {"conflict": 0, "unclear": 1, "needs_one_layer": 2, "adequate": 3}


def _merge_adequacy(old: str | None, new: str | None) -> str | None:
    if not old:
        return new
    if not new:
        return old
    return min([old, new], key=lambda item: ADEQUACY_ORDER.get(item, 99))


def _source_text_for_delta(root: Path, delta: dict[str, Any]) -> str | None:
    paper_index = read_json(root / ".quiver" / "artifacts" / "paper_index.json", default={}) or {}
    paper_paths = {paper.get("id"): paper.get("path") for paper in paper_index.get("papers", []) or []}
    source_rel = paper_paths.get(delta.get("paper_id"))
    if source_rel and (root / source_rel).exists():
        return (root / source_rel).read_text(encoding="utf-8", errors="replace")
    return None


def _paper_metadata_by_id(root: Path) -> dict[str, dict[str, Any]]:
    paper_index = read_json(root / ".quiver" / "artifacts" / "paper_index.json", default={}) or {}
    result: dict[str, dict[str, Any]] = {}
    for paper in paper_index.get("papers", []) or []:
        paper_id = paper.get("id")
        if not paper_id:
            continue
        result[paper_id] = {key: paper[key] for key in PUBLIC_PAPER_FIELDS if key in paper}
    return result


def merge_deltas(
    root: Path,
    *,
    fail_on_error: bool = True,
    seed_existing: bool = False,
    delta_paths: list[Path] | None = None,
) -> dict[str, Any]:
    root = require_project(root)
    metadata = read_project_metadata(root)
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    papers: dict[str, dict[str, Any]] = {}
    validation_items: list[dict[str, Any]] = []
    paper_metadata = _paper_metadata_by_id(root)

    if seed_existing:
        existing_graph = read_json(root / "results" / "normalized" / "concept_graph.json", default={}) or {}
        for paper in existing_graph.get("papers", []) or []:
            if paper.get("id"):
                papers[paper["id"]] = paper
        for node in existing_graph.get("nodes", []) or []:
            if node.get("id"):
                nodes[node["id"]] = node
        for edge in existing_graph.get("edges", []) or []:
            dependent = edge.get("dependent")
            prerequisite = edge.get("prerequisite")
            relation = edge.get("relation")
            if dependent and prerequisite and relation:
                edges[(dependent, prerequisite, relation)] = edge

    selected_delta_paths = delta_paths if delta_paths is not None else sorted((root / "results" / "deltas").glob("*.json"))
    selected_delta_paths = [path if path.is_absolute() else root / path for path in selected_delta_paths]
    deltas = [(path, read_json(path, default={}) or {}) for path in selected_delta_paths]
    known_delta_nodes = {
        node.get("canonical_id")
        for _, delta in deltas
        for node in delta.get("nodes", []) or []
        if isinstance(node, dict) and node.get("canonical_id")
    }
    validation_known_nodes = set(nodes) | known_delta_nodes

    for path, delta in deltas:
        paper_id = delta.get("paper_id") or path.stem
        issues = validate_delta(delta, existing_nodes=validation_known_nodes, source_text=_source_text_for_delta(root, delta))
        errors = [issue for issue in issues if issue["severity"] == "error"]
        validation_items.append(
            {"path": path.relative_to(root).as_posix(), "paper_id": paper_id, "errors": len(errors), "warnings": len(issues) - len(errors)}
        )
        if errors and fail_on_error:
            raise ValueError(f"cannot merge invalid delta {path}: {errors[0]['message']}")
        paper_row = dict(paper_metadata.get(paper_id, {}))
        paper_row["id"] = paper_id
        paper_row["title"] = delta.get("paper_title") or paper_row.get("title") or paper_id
        papers[paper_id] = paper_row

        for node in delta.get("nodes", []) or []:
            cid = node.get("canonical_id")
            if not cid:
                continue
            existing = nodes.get(cid)
            if existing is None:
                nodes[cid] = {
                    "id": cid,
                    "label": node.get("label") or cid,
                    "entity_type": node.get("entity_type"),
                    "ontology_status": node.get("ontology_status"),
                    "local_role": node.get("local_role"),
                    "aliases": node.get("aliases", []) or [],
                    "summary": node.get("summary") or "",
                    "confidence": node.get("confidence"),
                    "adequacy": node.get("adequacy"),
                    "ontology_statuses": [node.get("ontology_status")] if node.get("ontology_status") else [],
                    "paper_ids": [paper_id],
                    "evidence": node.get("evidence", []) or [],
                }
            else:
                existing["aliases"] = _merge_unique(existing.get("aliases", []), node.get("aliases", []) or [])
                existing["paper_ids"] = _merge_unique(existing.get("paper_ids", []), [paper_id])
                existing["evidence"] = _merge_unique(existing.get("evidence", []), node.get("evidence", []) or [])
                existing["adequacy"] = _merge_adequacy(existing.get("adequacy"), node.get("adequacy"))
                existing["ontology_statuses"] = _merge_unique(
                    existing.get("ontology_statuses", []),
                    [node.get("ontology_status")] if node.get("ontology_status") else [],
                )
                if not existing.get("summary") and node.get("summary"):
                    existing["summary"] = node["summary"]

        for edge in delta.get("edges", []) or []:
            dependent = edge.get("dependent")
            prerequisite = edge.get("prerequisite")
            relation = edge.get("relation")
            if not dependent or not prerequisite or not relation:
                continue
            key = (dependent, prerequisite, relation)
            existing = edges.get(key)
            if existing is None:
                edges[key] = {
                    "id": f"{dependent}__{relation}__{prerequisite}",
                    "dependent": dependent,
                    "prerequisite": prerequisite,
                    "relation": relation,
                    "confidence": edge.get("confidence"),
                    "paper_ids": [paper_id],
                    "evidence": edge.get("evidence", []) or [],
                }
            else:
                existing["paper_ids"] = _merge_unique(existing.get("paper_ids", []), [paper_id])
                existing["evidence"] = _merge_unique(existing.get("evidence", []), edge.get("evidence", []) or [])

    graph = {
        "schema_version": "quiver.graph.v1",
        "dataset": {
            "id": metadata["id"],
            "title": metadata["title"],
            "updated_at": now_iso(),
        },
        "papers": [papers[key] for key in sorted(papers)],
        "nodes": [nodes[key] for key in sorted(nodes)],
        "edges": [edges[key] for key in sorted(edges)],
        "validation": validation_items,
    }
    write_json(root / "results" / "normalized" / "concept_graph.json", graph)
    append_event(root, "merge", {"nodes": len(graph["nodes"]), "edges": len(graph["edges"])})
    return graph
