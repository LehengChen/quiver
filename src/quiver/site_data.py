"""Presentation-oriented data export for the static site."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from quiver.project import now_iso, read_json, read_project_metadata, require_project

TOPICAL_RELATIONS = {"belongs_to_topic"}


def _count_rows(counter: Counter[str]) -> list[dict[str, Any]]:
    return [{"key": key, "count": count} for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))]


def _paper_titles(graph: dict[str, Any]) -> dict[str, str]:
    return {paper.get("id"): paper.get("title") or paper.get("id") for paper in graph.get("papers", []) or [] if paper.get("id")}


ADEQUACY_LABELS = {
    "needs_one_layer": "needs one more layer",
    "unclear": "has unclear context",
    "conflict": "has conflicting context",
}


def _items_by_paper(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_paper: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        for paper_id in item.get("paper_ids", []) or []:
            by_paper.setdefault(paper_id, []).append(item)
    return by_paper


def _validation_warning_by_paper(graph: dict[str, Any]) -> dict[str, int]:
    warnings: dict[str, int] = {}
    for row in graph.get("validation", []) or []:
        paper_id = row.get("paper_id") or Path(row.get("path") or "").stem
        if paper_id:
            warnings[paper_id] = warnings.get(paper_id, 0) + int(row.get("warnings") or 0)
    return warnings


def _paper_summaries(graph: dict[str, Any]) -> list[dict[str, Any]]:
    titles = _paper_titles(graph)
    warnings = _validation_warning_by_paper(graph)
    nodes_by_paper = _items_by_paper(graph.get("nodes", []) or [])
    edges_by_paper = _items_by_paper(graph.get("edges", []) or [])
    rows = []
    for paper_id, title in sorted(titles.items()):
        nodes = nodes_by_paper.get(paper_id, [])
        edges = edges_by_paper.get(paper_id, [])
        rows.append(
            {
                "id": paper_id,
                "title": title,
                "concepts": len(nodes),
                "unique_concepts": len([node for node in nodes if len(node.get("paper_ids", []) or []) == 1]),
                "reused_concepts": len([node for node in nodes if len(node.get("paper_ids", []) or []) > 1]),
                "dependency_links": len(edges),
                "evidence_warnings": warnings.get(paper_id, 0),
                "concepts_needing_context": len([node for node in nodes if node.get("adequacy") not in (None, "adequate")]),
            }
        )
    return rows


def _frontier_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for node in nodes:
        adequacy = node.get("adequacy")
        if adequacy in (None, "adequate"):
            continue
        reasons = []
        if adequacy:
            reasons.append(ADEQUACY_LABELS.get(adequacy, "needs more context"))
        if node.get("confidence") == "low":
            reasons.append("low confidence")
        if node.get("local_role") == "frontier":
            reasons.append("frontier concept")
        rows.append(
            {
                "id": node.get("id"),
                "label": node.get("label") or node.get("id"),
                "reason": "; ".join(reasons) or "needs context",
                "adequacy": node.get("adequacy"),
                "confidence": node.get("confidence"),
                "local_role": node.get("local_role"),
                "paper_ids": node.get("paper_ids", []) or [],
            }
        )
    rows.sort(key=lambda item: (item.get("adequacy") or "", item.get("id") or ""))
    return rows


def _reused_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {
            "id": node.get("id"),
            "label": node.get("label") or node.get("id"),
            "paper_ids": node.get("paper_ids", []) or [],
            "paper_count": len(node.get("paper_ids", []) or []),
        }
        for node in nodes
        if len(node.get("paper_ids", []) or []) > 1
    ]
    rows.sort(key=lambda item: (-item["paper_count"], item.get("id") or ""))
    return rows


def _overlap_warnings(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for node in nodes:
        statuses = node.get("ontology_statuses", []) or ([node.get("ontology_status")] if node.get("ontology_status") else [])
        unique = sorted({status for status in statuses if status})
        if len(unique) <= 1:
            continue
        rows.append(
            {
                "id": node.get("id"),
                "label": node.get("label") or node.get("id"),
                "ontology_statuses": unique,
                "paper_ids": node.get("paper_ids", []) or [],
            }
        )
    rows.sort(key=lambda item: item.get("id") or "")
    return rows


def build_site_payloads(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = require_project(root)
    graph = read_json(root / "results" / "normalized" / "concept_graph.json", default={}) or {}
    metadata = read_project_metadata(root)
    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []
    relation_names = sorted({edge.get("relation") for edge in edges if edge.get("relation")})
    paper_summaries = _paper_summaries(graph)
    frontier = _frontier_nodes(nodes)
    reused = _reused_nodes(nodes)
    overlaps = _overlap_warnings(nodes)
    evidence_warnings = sum(row["evidence_warnings"] for row in paper_summaries)
    generated_at = now_iso()

    analysis = {
        "schema_version": "quiver.site_analysis.v1",
        "generated_at": generated_at,
        "summary": {
            "papers": len(graph.get("papers", []) or []),
            "concepts": len(nodes),
            "dependencies": len(edges),
            "concepts_needing_context": len(frontier),
            "reused_concepts": len(reused),
            "overlapping_concepts": len(overlaps),
            "evidence_warnings": evidence_warnings,
        },
        "counts": {
            "relations": _count_rows(Counter(edge.get("relation") or "unknown" for edge in edges)),
            "entity_types": _count_rows(Counter(node.get("entity_type") or "unknown" for node in nodes)),
            "local_roles": _count_rows(Counter(node.get("local_role") or "unknown" for node in nodes)),
            "adequacy": _count_rows(Counter(node.get("adequacy") or "unknown" for node in nodes)),
            "confidence": _count_rows(Counter(node.get("confidence") or "unknown" for node in nodes)),
        },
        "paper_summaries": paper_summaries,
        "frontier_nodes": frontier,
        "reused_nodes": reused,
        "overlap_warnings": overlaps,
        "relation_groups": {
            "strict_dependency": [name for name in relation_names if name not in TOPICAL_RELATIONS],
            "topical": [name for name in relation_names if name in TOPICAL_RELATIONS],
        },
    }
    manifest = {
        "schema_version": "quiver.site_manifest.v1",
        "project_id": metadata["id"],
        "title": metadata["title"],
        "generated_at": generated_at,
        "source_graph": "results/normalized/concept_graph.json",
        "files": ["index.html", "graph.json", "analysis.json", "manifest.json"],
    }
    return graph, analysis, manifest
