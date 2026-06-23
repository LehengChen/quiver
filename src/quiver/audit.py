"""Run-level audit reports for supervised extraction batches."""

from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher
import re
from pathlib import Path
from typing import Any

from quiver.project import read_json, read_jsonl, require_project, write_json


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _terminal_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    terminal_names = {"run_finished", "run_failed"}
    for event in reversed(events):
        if event.get("event") in terminal_names:
            return event
    return events[-1] if events else None


def _paper_event_summary(events: list[dict[str, Any]], summary_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    papers: dict[str, dict[str, Any]] = {}
    starts: dict[str, float] = {}

    for event in events:
        payload = event.get("payload") or {}
        paper_id = payload.get("paper_id")
        if not paper_id:
            continue
        item = papers.setdefault(paper_id, {"paper_id": paper_id, "events": []})
        item["events"].append(event.get("event"))
        if event.get("event") == "paper_started":
            item["index"] = payload.get("index")
            item["pre_graph"] = payload.get("pre_graph")
            item["delta_exists"] = payload.get("delta_exists")
        if event.get("event") == "extract_started":
            starts[paper_id] = float(event.get("elapsed_seconds") or 0)
        if event.get("event") == "extract_finished" and paper_id in starts:
            elapsed = float(event.get("elapsed_seconds") or 0) - starts[paper_id]
            item["extract_seconds"] = round(max(elapsed, 0.0), 3)
        if event.get("event") == "validation_finished":
            for key in ("errors", "warnings", "error_delta", "warning_delta", "delta_validation"):
                if key in payload:
                    item_key = {
                        "errors": "validation_errors",
                        "warnings": "validation_warnings",
                        "error_delta": "validation_error_delta",
                        "warning_delta": "validation_warning_delta",
                        "delta_validation": "validation_delta",
                    }[key]
                    item[item_key] = payload[key]
        if event.get("event") in {"paper_skipped_existing_delta", "merge_finished", "paper_failed"}:
            item.update({key: payload.get(key) for key in ("status", "nodes", "edges") if key in payload})

    for summary_item in summary_items:
        paper_id = summary_item.get("paper_id")
        if not paper_id:
            continue
        item = papers.setdefault(paper_id, {"paper_id": paper_id, "events": []})
        for key in (
            "status",
            "nodes",
            "edges",
            "validation_errors",
            "validation_warnings",
            "validation_error_delta",
            "validation_warning_delta",
            "validation_delta",
            "delta_path",
            "delta_snapshot",
        ):
            if key in summary_item:
                item[key] = summary_item[key]

    return sorted(papers.values(), key=lambda item: (item.get("index", 999999), item["paper_id"]))


def _validation_report_order(events: list[dict[str, Any]]) -> dict[str, int]:
    order: dict[str, int] = {}
    for event in events:
        if event.get("event") != "validation_finished":
            continue
        payload = event.get("payload") or {}
        path = payload.get("path")
        if path:
            order[Path(path).name] = int(event.get("seq") or len(order) + 1)
    return order


def _json_path_value(obj: Any, path: str | None) -> Any:
    if not path:
        return None
    cur = obj
    for part in path.split("."):
        match = re.fullmatch(r"([A-Za-z0-9_]+)(?:\[(\d+)\])?", part)
        if not match:
            return None
        key, index_text = match.groups()
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
        if index_text is not None:
            if not isinstance(cur, list):
                return None
            index = int(index_text)
            if index >= len(cur):
                return None
            cur = cur[index]
    return cur


def _evidence_entry_count(delta: dict[str, Any]) -> int:
    count = 0
    for node in delta.get("nodes", []) or []:
        count += len(node.get("evidence", []) or []) if isinstance(node, dict) else 0
    for edge in delta.get("edges", []) or []:
        count += len(edge.get("evidence", []) or []) if isinstance(edge, dict) else 0
    return count


def _validation_reports(root: Path, run_dir: Path, events: list[dict[str, Any]]) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    total = Counter()
    sample_issues: list[dict[str, Any]] = []
    order = _validation_report_order(events)

    paths = sorted(run_dir.glob("validation*.json"), key=lambda path: (order.get(path.name, 999999), path.name))
    for path in paths:
        report = read_json(path, default={}) or {}
        items = report.get("items", []) or []
        issue_messages = Counter()
        delta_rows: list[dict[str, Any]] = []
        errors = 0
        warnings = 0
        for item in items:
            errors += int(item.get("errors") or 0)
            warnings += int(item.get("warnings") or 0)
            issue_locations = Counter()
            delta_path = root / (item.get("path") or "")
            delta_obj = read_json(delta_path, default={}) or {}
            for issue in item.get("issues", []) or []:
                message = issue.get("message") or "unknown"
                severity = issue.get("severity") or "unknown"
                issue_path = issue.get("path") or ""
                issue_messages[f"{severity}: {message}"] += 1
                if issue_path.startswith("nodes[") or issue_path.startswith("nodes."):
                    issue_locations["node"] += 1
                elif issue_path.startswith("edges[") or issue_path.startswith("edges."):
                    issue_locations["edge"] += 1
                else:
                    issue_locations["other"] += 1
                if len(sample_issues) < 12:
                    value = _json_path_value(delta_obj, issue.get("path"))
                    quote_preview = value if isinstance(value, str) else None
                    sample_issues.append(
                        {
                            "report": _rel(root, path),
                            "delta": item.get("path"),
                            "paper_id": delta_obj.get("paper_id") if isinstance(delta_obj, dict) else None,
                            "path": issue.get("path"),
                            "severity": severity,
                            "message": message,
                            "quote_preview": quote_preview[:240] if quote_preview else None,
                        }
                    )
            delta_rows.append(
                {
                    "path": item.get("path"),
                    "paper_id": delta_obj.get("paper_id") if isinstance(delta_obj, dict) else None,
                    "errors": int(item.get("errors") or 0),
                    "warnings": int(item.get("warnings") or 0),
                    "issue_locations": dict(sorted(issue_locations.items())),
                    "evidence_entries": _evidence_entry_count(delta_obj) if isinstance(delta_obj, dict) else 0,
                }
            )
        total["errors"] += errors
        total["warnings"] += warnings
        reports.append(
            {
                "path": _rel(root, path),
                "items": len(items),
                "errors": errors,
                "warnings": warnings,
                "messages": dict(sorted(issue_messages.items())),
                "deltas": delta_rows,
            }
        )

    return {
        "reports": reports,
        "report_count": len(reports),
        "summed_report_errors": total["errors"],
        "summed_report_warnings": total["warnings"],
        "latest_errors": reports[-1]["errors"] if reports else 0,
        "latest_warnings": reports[-1]["warnings"] if reports else 0,
        "latest": reports[-1] if reports else None,
        "sample_issues": sample_issues,
    }


def _enrich_paper_validation_deltas(papers: list[dict[str, Any]], validation: dict[str, Any]) -> None:
    by_paper: dict[str, dict[str, Any]] = {}
    for report in validation.get("reports", []) or []:
        deltas = [item for item in report.get("deltas", []) or [] if isinstance(item, dict) and item.get("paper_id")]
        if deltas:
            row = deltas[-1]
            by_paper[str(row["paper_id"])] = row
    latest = validation.get("latest") or {}
    for item in latest.get("deltas", []) or []:
        if isinstance(item, dict) and item.get("paper_id"):
            by_paper.setdefault(str(item["paper_id"]), item)
    for paper in papers:
        if "validation_warning_delta" in paper and "validation_error_delta" in paper:
            continue
        row = by_paper.get(paper.get("paper_id"))
        if not row:
            continue
        errors = int(row.get("errors") or 0)
        warnings = int(row.get("warnings") or 0)
        paper["validation_error_delta"] = errors
        paper["validation_warning_delta"] = warnings
        paper["validation_delta"] = {
            "delta_path": row.get("path"),
            "error_delta": errors,
            "warning_delta": warnings,
            "errors": errors,
            "warnings": warnings,
            "issue_locations": row.get("issue_locations", {}) or {},
            "evidence_entries": int(row.get("evidence_entries") or 0),
        }


def _fill_validation_from_papers(validation: dict[str, Any], papers: list[dict[str, Any]]) -> None:
    if validation.get("report_count"):
        return
    delta_rows = []
    for paper in papers:
        row = paper.get("validation_delta")
        if not isinstance(row, dict):
            continue
        delta_rows.append(
            {
                "path": row.get("delta_path"),
                "paper_id": paper.get("paper_id"),
                "errors": int(row.get("errors") or row.get("error_delta") or 0),
                "warnings": int(row.get("warnings") or row.get("warning_delta") or 0),
                "issue_locations": row.get("issue_locations", {}) or {},
                "evidence_entries": int(row.get("evidence_entries") or 0),
            }
        )
    if not delta_rows:
        return
    errors = sum(row["errors"] for row in delta_rows)
    warnings = sum(row["warnings"] for row in delta_rows)
    validation["latest_errors"] = errors
    validation["latest_warnings"] = warnings
    validation["latest"] = {
        "path": None,
        "items": len(delta_rows),
        "errors": errors,
        "warnings": warnings,
        "messages": {},
        "deltas": delta_rows,
        "source": "summary.validation_delta",
    }


def _frontier(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    items = [
        {
            "id": node.get("id"),
            "label": node.get("label"),
            "adequacy": node.get("adequacy") or "unknown",
            "paper_ids": node.get("paper_ids", []) or [],
        }
        for node in nodes
        if node.get("adequacy") not in (None, "adequate")
    ]
    counts = Counter(item["adequacy"] for item in items)
    return {
        "count": len(items),
        "by_adequacy": dict(sorted(counts.items())),
        "items": sorted(items, key=lambda item: (item["adequacy"], item["id"] or ""))[:50],
    }


def _similar_candidates(nodes: list[dict[str, Any]], *, threshold: float, limit: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    entries = [
        {
            "id": str(node.get("id") or ""),
            "label": str(node.get("label") or ""),
            "aliases": [str(alias) for alias in node.get("aliases", []) or []],
        }
        for node in nodes
        if node.get("id")
    ]
    for left_i, left in enumerate(entries):
        for right in entries[left_i + 1 :]:
            id_score = SequenceMatcher(None, left["id"], right["id"]).ratio()
            label_score = SequenceMatcher(None, left["label"].lower(), right["label"].lower()).ratio()
            score = max(id_score, label_score)
            if score < threshold:
                continue
            candidates.append(
                {
                    "left": left["id"],
                    "right": right["id"],
                    "left_label": left["label"],
                    "right_label": right["label"],
                    "score": round(score, 3),
                }
            )
    candidates.sort(key=lambda item: (-item["score"], item["left"], item["right"]))
    return candidates[:limit]


def _ontology_status_conflicts(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conflicts = []
    for node in nodes:
        statuses = node.get("ontology_statuses", []) or []
        if not statuses and node.get("ontology_status"):
            statuses = [node["ontology_status"]]
        unique_statuses = sorted({status for status in statuses if status})
        if len(unique_statuses) <= 1:
            continue
        conflicts.append(
            {
                "id": node.get("id"),
                "label": node.get("label"),
                "ontology_status": node.get("ontology_status"),
                "ontology_statuses": unique_statuses,
                "paper_ids": node.get("paper_ids", []) or [],
            }
        )
    return sorted(conflicts, key=lambda item: item["id"] or "")


def _reuse_summary(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    items = [
        {
            "id": node.get("id"),
            "label": node.get("label"),
            "paper_ids": node.get("paper_ids", []) or [],
            "paper_count": len(node.get("paper_ids", []) or []),
        }
        for node in nodes
        if len(node.get("paper_ids", []) or []) > 1
    ]
    items.sort(key=lambda item: (-item["paper_count"], item["id"] or ""))
    return {"multi_paper_node_count": len(items), "items": items[:50]}


def _review_queue(nodes: list[dict[str, Any]], conflicts: list[dict[str, Any]], *, limit: int = 80) -> list[dict[str, Any]]:
    conflict_ids = {item["id"] for item in conflicts}
    rows = []
    for node in nodes:
        reasons = []
        adequacy = node.get("adequacy") or "unknown"
        confidence = node.get("confidence") or "unknown"
        local_role = node.get("local_role") or "unknown"
        node_id = node.get("id")
        if node_id in conflict_ids:
            reasons.append("ontology_status_conflict")
        if adequacy in {"unclear", "conflict"}:
            reasons.append(f"adequacy:{adequacy}")
        elif adequacy == "needs_one_layer":
            reasons.append("needs_one_layer")
        if confidence == "low":
            reasons.append("low_confidence")
        elif confidence == "medium" and local_role in {"main", "frontier"}:
            reasons.append("medium_confidence_main_or_frontier")
        if local_role == "frontier":
            reasons.append("frontier_role")
        if local_role == "main" and adequacy == "needs_one_layer":
            reasons.append("main_needs_one_layer")
        if not reasons:
            continue
        priority = 3
        if "ontology_status_conflict" in reasons or "low_confidence" in reasons or adequacy in {"unclear", "conflict"}:
            priority = 0
        elif local_role == "frontier" or (local_role == "main" and adequacy == "needs_one_layer"):
            priority = 1
        elif adequacy == "needs_one_layer":
            priority = 2
        rows.append(
            {
                "priority": priority,
                "id": node_id,
                "label": node.get("label"),
                "reasons": reasons,
                "adequacy": adequacy,
                "confidence": confidence,
                "local_role": local_role,
                "paper_ids": node.get("paper_ids", []) or [],
            }
        )
    rows.sort(key=lambda item: (item["priority"], item["id"] or ""))
    return rows[:limit]


def _artifact_summary(root: Path, run_dir: Path, papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for paper in papers:
        paper_id = paper["paper_id"]
        paper_dir = run_dir / "papers" / paper_id
        files = sorted(path.name for path in paper_dir.glob("*") if path.is_file())
        rows.append(
            {
                "paper_id": paper_id,
                "path": _rel(root, paper_dir) if paper_dir.exists() else None,
                "files": files,
                "has_delta_snapshot": "delta.json" in files,
                "has_prompt_snapshot": "prompt.md" in files,
                "has_response_snapshot": "last_message.json" in files,
            }
        )
    return rows


def _graph_summary(root: Path, *, similar_threshold: float, similar_limit: int) -> dict[str, Any]:
    graph = read_json(root / "results" / "normalized" / "concept_graph.json", default={}) or {}
    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []
    relation_counts = Counter(edge.get("relation") or "unknown" for edge in edges)
    duplicate_ids = [node_id for node_id, count in Counter(node.get("id") for node in nodes).items() if node_id and count > 1]
    conflicts = _ontology_status_conflicts(nodes)
    return {
        "path": "results/normalized/concept_graph.json",
        "papers": len(graph.get("papers", []) or []),
        "nodes": len(nodes),
        "edges": len(edges),
        "relations": dict(sorted(relation_counts.items())),
        "duplicate_node_ids": sorted(duplicate_ids),
        "reuse": _reuse_summary(nodes),
        "ontology_status_conflicts": conflicts,
        "review_queue": _review_queue(nodes, conflicts),
        "frontier": _frontier(nodes),
        "similar_candidates": _similar_candidates(nodes, threshold=similar_threshold, limit=similar_limit),
    }


def audit_run(
    root: Path,
    run_id: str,
    *,
    similar_threshold: float = 0.86,
    similar_limit: int = 50,
    write: bool = True,
) -> dict[str, Any]:
    """Build and optionally persist a structured audit report for a serial run."""
    root = require_project(root)
    run_dir = root / "results" / "runs" / run_id
    events_path = run_dir / "events.jsonl"
    summary_path = run_dir / "summary.json"
    if not run_dir.exists():
        raise FileNotFoundError(f"run not found: {run_id}")

    events = read_jsonl(events_path)
    summary = read_json(summary_path, default={}) or {}
    summary_items = summary.get("items", []) or []
    papers = _paper_event_summary(events, summary_items)
    terminal = _terminal_event(events)
    event_counts = Counter(event.get("event") or "unknown" for event in events)

    validation = _validation_reports(root, run_dir, events)
    _enrich_paper_validation_deltas(papers, validation)
    _fill_validation_from_papers(validation, papers)

    audit = {
        "schema_version": "quiver.run_audit.v1",
        "run_id": run_id,
        "run_dir": _rel(root, run_dir),
        "status": (summary.get("status") or ((terminal or {}).get("payload") or {}).get("status") or "unknown"),
        "summary_path": _rel(root, summary_path) if summary_path.exists() else None,
        "events_path": _rel(root, events_path) if events_path.exists() else None,
        "event_count": len(events),
        "event_counts": dict(sorted(event_counts.items())),
        "terminal_event": terminal,
        "papers": papers,
        "artifacts": _artifact_summary(root, run_dir, papers),
        "validation": validation,
        "graph": _graph_summary(root, similar_threshold=similar_threshold, similar_limit=similar_limit),
    }

    if write:
        write_json(run_dir / "audit.json", audit)
    return audit
