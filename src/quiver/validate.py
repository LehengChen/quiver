"""Validation for graph deltas and merged graphs."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from jsonschema import Draft202012Validator

from quiver.concept_quality import concept_node_exclusion_reason, has_document_result_ref
from quiver.project import append_event, read_json, require_project
from quiver.schema_defs import GRAPH_DELTA_SCHEMA

ENTITY_TYPES = {"definition", "object", "method", "property", "topic", "notation", "primitive"}
ONTOLOGY_STATUS = {"new", "existing", "refined", "uncertain"}
LOCAL_ROLES = {"main", "supporting", "background", "frontier"}
CONFIDENCE = {"high", "medium", "low"}
ADEQUACY = {"adequate", "needs_one_layer", "conflict", "unclear"}
RELATIONS = {
    "definition_depends_on",
    "uses_method",
    "has_property",
    "constructed_using",
    "specializes",
    "belongs_to_topic",
    "has_primitive",
    "computed_by",
}
SCHEMA_VALIDATOR = Draft202012Validator(GRAPH_DELTA_SCHEMA)


def _issue(path: str, severity: str, message: str) -> dict[str, str]:
    return {"path": path, "severity": severity, "message": message}


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _token_stream(text: str) -> str:
    return "".join(re.findall(r"[a-z0-9]+", text.lower()))


def _parts_in_order(haystack: str, parts: list[str]) -> bool:
    pos = 0
    for part in parts:
        idx = haystack.find(part, pos)
        if idx == -1:
            return False
        pos = idx + len(part)
    return True


def _quote_matches_source(quote: str, source_text: str) -> bool:
    haystack = _compact_text(source_text)
    compact_quote = _compact_text(quote)
    if compact_quote in haystack:
        return True

    source_tokens = _token_stream(source_text)
    quote_tokens = _token_stream(quote)
    if quote_tokens and quote_tokens in source_tokens:
        return True

    if "..." in quote or "…" in quote:
        raw_parts = re.split(r"\.\.\.|…", quote)
        compact_parts = [_compact_text(part) for part in raw_parts if _compact_text(part)]
        token_parts = [_token_stream(part) for part in raw_parts if _token_stream(part)]
        if compact_parts and _parts_in_order(haystack, compact_parts):
            return True
        if token_parts and _parts_in_order(source_tokens, token_parts):
            return True

    return False


def _validate_evidence_text(
    issues: list[dict[str, str]], payload: dict[str, Any], source_text: str | None
) -> None:
    if not source_text:
        return
    for kind in ("nodes", "edges"):
        for idx, item in enumerate(payload.get(kind, []) or []):
            if not isinstance(item, dict):
                continue
            for eidx, evidence in enumerate(item.get("evidence", []) or []):
                if not isinstance(evidence, dict):
                    continue
                quote = evidence.get("quote")
                if isinstance(quote, str) and quote and not _quote_matches_source(quote, source_text):
                    issues.append(
                        _issue(
                            f"{kind}[{idx}].evidence[{eidx}].quote",
                            "warning",
                            "evidence quote was not found verbatim in the source text",
                        )
                    )


def validate_delta(
    payload: dict[str, Any], *, existing_nodes: set[str] | None = None, source_text: str | None = None
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    existing_nodes = existing_nodes or set()
    for error in sorted(SCHEMA_VALIDATOR.iter_errors(payload), key=lambda item: list(item.path)):
        path = ".".join(str(part) for part in error.path) or "$"
        issues.append(_issue(path, "error", error.message))
    if payload.get("schema_version") != "quiver.graph_delta.v1":
        issues.append(_issue("schema_version", "error", "expected quiver.graph_delta.v1"))
    if not isinstance(payload.get("paper_id"), str) or not payload.get("paper_id"):
        issues.append(_issue("paper_id", "error", "paper_id is required"))
    nodes = payload.get("nodes")
    edges = payload.get("edges")
    if not isinstance(nodes, list):
        issues.append(_issue("nodes", "error", "nodes must be a list"))
        nodes = []
    if not isinstance(edges, list):
        issues.append(_issue("edges", "error", "edges must be a list"))
        edges = []

    ids: set[str] = set()
    for idx, node in enumerate(nodes):
        path = f"nodes[{idx}]"
        if not isinstance(node, dict):
            issues.append(_issue(path, "error", "node must be an object"))
            continue
        cid = node.get("canonical_id")
        if not isinstance(cid, str) or not cid:
            issues.append(_issue(f"{path}.canonical_id", "error", "canonical_id is required"))
        elif cid in ids:
            issues.append(_issue(f"{path}.canonical_id", "error", f"duplicate canonical_id: {cid}"))
        else:
            ids.add(cid)
        if not node.get("label"):
            issues.append(_issue(f"{path}.label", "error", "label is required"))
        if node.get("entity_type") not in ENTITY_TYPES:
            issues.append(_issue(f"{path}.entity_type", "error", "invalid entity_type"))
        exclusion_reason = concept_node_exclusion_reason(node)
        if exclusion_reason:
            issues.append(_issue(path, "error", exclusion_reason))
        if has_document_result_ref(str(node.get("summary") or "")):
            issues.append(
                _issue(
                    f"{path}.summary",
                    "warning",
                    "summary contains a paper-local numbered result reference; keep numbered theorem/lemma/proposition references in evidence when possible",
                )
            )
        if node.get("ontology_status") not in ONTOLOGY_STATUS:
            issues.append(_issue(f"{path}.ontology_status", "error", "invalid ontology_status"))
        if node.get("local_role") not in LOCAL_ROLES:
            issues.append(_issue(f"{path}.local_role", "error", "invalid local_role"))
        if node.get("confidence") not in CONFIDENCE:
            issues.append(_issue(f"{path}.confidence", "error", "invalid confidence"))
        if node.get("adequacy") not in ADEQUACY:
            issues.append(_issue(f"{path}.adequacy", "warning", "adequacy should be explicit"))
        if not node.get("evidence"):
            issues.append(_issue(f"{path}.evidence", "warning", "node has no evidence spans"))

    known_ids = ids | existing_nodes
    edge_keys: set[tuple[str, str, str]] = set()
    for idx, edge in enumerate(edges):
        path = f"edges[{idx}]"
        if not isinstance(edge, dict):
            issues.append(_issue(path, "error", "edge must be an object"))
            continue
        dependent = edge.get("dependent")
        prerequisite = edge.get("prerequisite")
        relation = edge.get("relation")
        if not isinstance(dependent, str) or not dependent:
            issues.append(_issue(f"{path}.dependent", "error", "dependent is required"))
        elif dependent not in known_ids:
            issues.append(_issue(f"{path}.dependent", "error", f"unknown dependent node: {dependent}"))
        if not isinstance(prerequisite, str) or not prerequisite:
            issues.append(_issue(f"{path}.prerequisite", "error", "prerequisite is required"))
        elif prerequisite not in known_ids:
            issues.append(_issue(f"{path}.prerequisite", "error", f"unknown prerequisite node: {prerequisite}"))
        if relation not in RELATIONS:
            issues.append(_issue(f"{path}.relation", "error", "invalid relation"))
        if edge.get("confidence") not in CONFIDENCE:
            issues.append(_issue(f"{path}.confidence", "error", "invalid confidence"))
        if dependent and prerequisite and relation:
            key = (dependent, prerequisite, relation)
            if key in edge_keys:
                issues.append(_issue(path, "warning", "duplicate edge in delta"))
            edge_keys.add(key)
        if not edge.get("evidence"):
            issues.append(_issue(f"{path}.evidence", "warning", "edge has no evidence spans"))
    _validate_evidence_text(issues, payload, source_text)
    return issues


def validate_project(root: Path, *, delta_paths: list[Path] | None = None) -> dict[str, Any]:
    root = require_project(root)
    graph = read_json(root / "results" / "normalized" / "concept_graph.json", default={}) or {}
    existing_nodes = {node.get("id") for node in graph.get("nodes", []) or [] if node.get("id")}
    items: list[dict[str, Any]] = []
    selected_paths = delta_paths if delta_paths is not None else sorted((root / "results" / "deltas").glob("*.json"))
    selected_paths = [path if path.is_absolute() else root / path for path in selected_paths]
    for path in selected_paths:
        payload = read_json(path, default={}) or {}
        source_text = None
        paper_index = read_json(root / ".quiver" / "artifacts" / "paper_index.json", default={}) or {}
        paper_paths = {paper.get("id"): paper.get("path") for paper in paper_index.get("papers", []) or []}
        source_rel = paper_paths.get(payload.get("paper_id"))
        if source_rel and (root / source_rel).exists():
            source_text = (root / source_rel).read_text(encoding="utf-8", errors="replace")
        issues = validate_delta(payload, existing_nodes=existing_nodes, source_text=source_text)
        items.append(
            {
                "path": path.relative_to(root).as_posix(),
                "paper_id": payload.get("paper_id") or path.stem,
                "errors": len([i for i in issues if i["severity"] == "error"]),
                "warnings": len([i for i in issues if i["severity"] == "warning"]),
                "issues": issues,
            }
        )
    append_event(root, "validate", {"files": len(items), "errors": sum(item["errors"] for item in items)})
    return {"schema_version": "quiver.validation_report.v1", "items": items}
