"""Deterministic local search over registry, graph, and paper metadata."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from quiver.concept_quality import concept_node_exclusion_reason
from quiver.project import read_json, require_project


def _tokens(text: str) -> set[str]:
    return {tok.lower() for tok in re.findall(r"[A-Za-z0-9_]+", text) if len(tok) > 1}


def _score(query_tokens: set[str], haystack: str) -> float:
    hay_tokens = _tokens(haystack)
    if not query_tokens or not hay_tokens:
        return 0.0
    overlap = len(query_tokens & hay_tokens)
    substring_bonus = 1 if " ".join(sorted(query_tokens)) in haystack.lower() else 0
    return overlap / len(query_tokens) + substring_bonus


def _node_text(node: dict[str, Any]) -> str:
    parts = [
        str(node.get("id") or node.get("canonical_id") or ""),
        str(node.get("label") or node.get("canonical_name") or ""),
        str(node.get("summary") or ""),
        " ".join(node.get("aliases", []) or []),
    ]
    return " ".join(parts)


def search_local(root: Path, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
    root = require_project(root)
    query_tokens = _tokens(query)
    results: list[dict[str, Any]] = []

    graph = read_json(root / "results" / "normalized" / "concept_graph.json", default={}) or {}
    for node in graph.get("nodes", []) or []:
        if concept_node_exclusion_reason(node):
            continue
        text = _node_text(node)
        score = _score(query_tokens, text)
        if score > 0:
            results.append(
                {
                    "kind": "graph_node",
                    "id": node.get("id") or node.get("canonical_id"),
                    "label": node.get("label") or node.get("canonical_name"),
                    "summary": node.get("summary") or "",
                    "aliases": node.get("aliases", []) or [],
                    "score": round(score, 4),
                    "source": "results/normalized/concept_graph.json",
                }
            )

    pool = read_json(root / "registry" / "entity_pool.json", default={}) or {}
    for entity in pool.get("entities", []) or []:
        if concept_node_exclusion_reason(entity):
            continue
        text = _node_text(entity)
        score = _score(query_tokens, text)
        if score > 0:
            results.append(
                {
                    "kind": "registry_entity",
                    "id": entity.get("id") or entity.get("canonical_id"),
                    "label": entity.get("label") or entity.get("canonical_name"),
                    "summary": entity.get("summary") or "",
                    "aliases": entity.get("aliases", []) or [],
                    "score": round(score, 4),
                    "source": "registry/entity_pool.json",
                }
            )

    paper_index = read_json(root / ".quiver" / "artifacts" / "paper_index.json", default={}) or {}
    for paper in paper_index.get("papers", []) or []:
        text = f"{paper.get('id', '')} {paper.get('title', '')}"
        score = _score(query_tokens, text)
        if score > 0:
            results.append(
                {
                    "kind": "paper",
                    "id": paper.get("id"),
                    "label": paper.get("title"),
                    "score": round(score, 4),
                    "source": paper.get("path"),
                }
            )

    results.sort(key=lambda item: (-float(item["score"]), str(item["kind"]), str(item["id"])))
    return results[:limit]
