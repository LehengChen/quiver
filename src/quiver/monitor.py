"""Lightweight run monitoring without a full graph audit."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from quiver.project import append_jsonl, now_iso, read_json, read_jsonl, require_project


TERMINAL_EVENTS = {"run_finished", "run_failed"}
PAPER_DONE_EVENTS = {"merge_finished", "paper_skipped_existing_delta", "paper_failed"}
PHASES = {
    "paper_started": "started",
    "package_built": "packaged",
    "extract_prepared": "prepared",
    "extract_started": "extracting",
    "extract_finished": "extracted",
    "validation_finished": "validated",
}


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _resolve_output(root: Path, path: Path | None, default: Path) -> Path:
    if path is None:
        return default
    return path if path.is_absolute() else root / path


def _terminal_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("event") in TERMINAL_EVENTS:
            return event
    return None


def _status(events: list[dict[str, Any]], summary: dict[str, Any], terminal: dict[str, Any] | None) -> str:
    if summary.get("status"):
        return str(summary["status"])
    if terminal:
        payload = terminal.get("payload") or {}
        return str(payload.get("status") or "completed")
    return "running" if any(event.get("event") == "run_started" for event in events) else "unknown"


def _last_paper(events: list[dict[str, Any]]) -> str | None:
    for event in reversed(events):
        payload = event.get("payload") or {}
        if payload.get("paper_id"):
            return str(payload["paper_id"])
    return None


def _active_paper(events: list[dict[str, Any]], status: str) -> dict[str, Any] | None:
    if status not in {"running", "unknown"}:
        return None
    active: dict[str, Any] | None = None
    for event in events:
        payload = event.get("payload") or {}
        event_name = str(event.get("event") or "")
        if event_name in TERMINAL_EVENTS:
            active = None
            continue
        paper_id = payload.get("paper_id")
        if not paper_id:
            continue
        if event_name in PAPER_DONE_EVENTS:
            if active and active.get("paper_id") == paper_id:
                active = None
            continue
        index = payload.get("index")
        if index is None and active and active.get("paper_id") == paper_id:
            index = active.get("index")
        active = {
            "paper_id": str(paper_id),
            "phase": PHASES.get(event_name, event_name or "unknown"),
            "index": index,
            "last_event": event_name,
            "last_seq": event.get("seq"),
            "elapsed_seconds": event.get("elapsed_seconds"),
        }
    return active


def _progress(events: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, int | None]:
    total = None
    for event in events:
        if event.get("event") == "run_started":
            payload = event.get("payload") or {}
            paper_ids = payload.get("paper_ids")
            if isinstance(paper_ids, list):
                total = len(paper_ids)
    completed = sum(1 for event in events if event.get("event") in PAPER_DONE_EVENTS)
    summary_items = summary.get("items", []) or []
    if summary_items:
        completed = max(completed, len(summary_items))
        total = total if total is not None else len(summary_items)
    return {"completed": completed, "total": total}


def _issue_locations(issues: list[dict[str, Any]]) -> dict[str, int]:
    locations = Counter()
    for issue in issues:
        path = issue.get("path") or ""
        if path.startswith("nodes[") or path.startswith("nodes."):
            locations["node"] += 1
        elif path.startswith("edges[") or path.startswith("edges."):
            locations["edge"] += 1
        else:
            locations["other"] += 1
    return dict(sorted(locations.items()))


def _evidence_entry_count(delta: dict[str, Any]) -> int:
    count = 0
    for node in delta.get("nodes", []) or []:
        if isinstance(node, dict):
            count += len(node.get("evidence", []) or [])
    for edge in delta.get("edges", []) or []:
        if isinstance(edge, dict):
            count += len(edge.get("evidence", []) or [])
    return count


def _delta_validation_from_report(root: Path, report: dict[str, Any], paper_id: str | None) -> dict[str, Any] | None:
    if not paper_id:
        return None
    for item in report.get("items", []) or []:
        delta_path = root / (item.get("path") or "")
        delta = read_json(delta_path, default={}) or {}
        if not isinstance(delta, dict) or delta.get("paper_id") != paper_id:
            continue
        errors = int(item.get("errors") or 0)
        warnings = int(item.get("warnings") or 0)
        return {
            "delta_path": item.get("path"),
            "paper_id": paper_id,
            "error_delta": errors,
            "warning_delta": warnings,
            "errors": errors,
            "warnings": warnings,
            "issue_locations": _issue_locations(item.get("issues", []) or []),
            "evidence_entries": _evidence_entry_count(delta),
        }
    return None


def _latest_validation(root: Path, run_dir: Path, events: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    for event in reversed(events):
        if event.get("event") != "validation_finished":
            continue
        payload = event.get("payload") or {}
        report_path = run_dir / str(payload.get("path") or "")
        report = read_json(report_path, default={}) or {}
        delta_validation = payload.get("delta_validation")
        if not delta_validation:
            delta_validation = _delta_validation_from_report(root, report, payload.get("paper_id"))
        latest_path = _rel(root, report_path) if report_path.exists() else None
        errors = int(payload.get("errors") or sum(item.get("errors", 0) for item in report.get("items", []) or []))
        warnings = int(payload.get("warnings") or sum(item.get("warnings", 0) for item in report.get("items", []) or []))
        error_delta = int(payload.get("error_delta") or (delta_validation or {}).get("errors") or 0)
        warning_delta = int(payload.get("warning_delta") or (delta_validation or {}).get("warnings") or 0)
        return {
            "path": latest_path,
            "latest_path": latest_path,
            "paper_id": payload.get("paper_id"),
            "latest_errors": errors,
            "latest_warnings": warnings,
            "errors": errors,
            "warnings": warnings,
            "error_delta": error_delta,
            "warning_delta": warning_delta,
            "delta_validation": delta_validation,
        }

    for event in reversed(events):
        payload = event.get("payload") or {}
        delta_validation = payload.get("validation_delta") or payload.get("delta_validation")
        if not delta_validation and "validation_warning_delta" not in payload and "warning_delta" not in payload:
            continue
        error_delta = int(payload.get("validation_error_delta") or payload.get("error_delta") or (delta_validation or {}).get("errors") or 0)
        warning_delta = int(
            payload.get("validation_warning_delta") or payload.get("warning_delta") or (delta_validation or {}).get("warnings") or 0
        )
        return {
            "path": None,
            "latest_path": None,
            "paper_id": payload.get("paper_id"),
            "latest_errors": error_delta,
            "latest_warnings": warning_delta,
            "errors": error_delta,
            "warnings": warning_delta,
            "error_delta": error_delta,
            "warning_delta": warning_delta,
            "delta_validation": delta_validation,
        }

    items = summary.get("items", []) or []
    for item in reversed(items):
        if "validation_delta" not in item and "validation_warning_delta" not in item:
            continue
        errors = int(item.get("validation_errors") or item.get("validation_error_delta") or 0)
        warnings = int(item.get("validation_warnings") or item.get("validation_warning_delta") or 0)
        return {
            "path": None,
            "latest_path": None,
            "paper_id": item.get("paper_id"),
            "latest_errors": errors,
            "latest_warnings": warnings,
            "errors": errors,
            "warnings": warnings,
            "error_delta": int(item.get("validation_error_delta") or 0),
            "warning_delta": int(item.get("validation_warning_delta") or 0),
            "delta_validation": item.get("validation_delta"),
        }
    return {
        "path": None,
        "latest_path": None,
        "paper_id": None,
        "latest_errors": 0,
        "latest_warnings": 0,
        "errors": 0,
        "warnings": 0,
        "error_delta": 0,
        "warning_delta": 0,
    }


def _next_sample_id(path: Path) -> str:
    return f"sample-{len(read_jsonl(path)) + 1:03d}"


def monitor_run(
    root: Path,
    run_id: str,
    *,
    append: bool = False,
    output_path: Path | None = None,
    sample_id: str | None = None,
) -> dict[str, Any]:
    """Return a cheap run heartbeat and optionally append it as JSONL."""
    root = require_project(root)
    run_dir = root / "results" / "runs" / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"run not found: {run_id}")

    events_path = run_dir / "events.jsonl"
    summary_path = run_dir / "summary.json"
    events = read_jsonl(events_path)
    summary = read_json(summary_path, default={}) or {}
    terminal = _terminal_event(events)
    status = _status(events, summary, terminal)
    last = events[-1] if events else {}
    graph = read_json(root / "results" / "normalized" / "concept_graph.json", default={}) or {}
    output = _resolve_output(root, output_path, run_dir / "monitor.jsonl")

    sample = {
        "schema_version": "quiver.monitor_sample.v1",
        "sample_id": sample_id or (_next_sample_id(output) if append else "adhoc"),
        "ts": now_iso(),
        "run_id": run_id,
        "run_dir": _rel(root, run_dir),
        "status": status,
        "summary_path": _rel(root, summary_path) if summary_path.exists() else None,
        "events_path": _rel(root, events_path) if events_path.exists() else None,
        "event_count": len(events),
        "event_counts": dict(sorted(Counter(event.get("event") or "unknown" for event in events).items())),
        "last_event": last.get("event"),
        "last_seq": last.get("seq"),
        "elapsed_seconds": last.get("elapsed_seconds"),
        "last_paper": _last_paper(events),
        "active_paper": _active_paper(events, status),
        "progress": _progress(events, summary),
        "graph": {
            "path": "results/normalized/concept_graph.json",
            "papers": len(graph.get("papers", []) or []),
            "nodes": len(graph.get("nodes", []) or []),
            "edges": len(graph.get("edges", []) or []),
        },
        "validation": _latest_validation(root, run_dir, events, summary),
    }
    if append:
        append_jsonl(output, sample)
        sample["output_path"] = _rel(root, output)
    return sample
