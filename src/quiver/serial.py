"""Serial accumulated extraction runner."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

from quiver.codex import prepare_extract_requests, run_prepared_requests
from quiver.ingest import scan_papers
from quiver.merge import merge_deltas
from quiver.packages import build_packages
from quiver.project import append_event, append_jsonl, now_iso, now_stamp, read_json, require_project, write_json
from quiver.site import build_site
from quiver.validate import validate_delta, validate_project


def paper_ids_from_index(root: Path) -> list[str]:
    index = read_json(root / ".quiver" / "artifacts" / "paper_index.json", default={}) or {}
    return [paper["id"] for paper in index.get("papers", []) or [] if paper.get("id")]


def _issue_locations(issues: list[dict[str, Any]]) -> dict[str, int]:
    locations = {"node": 0, "edge": 0, "other": 0}
    for issue in issues:
        path = issue.get("path") or ""
        if path.startswith("nodes[") or path.startswith("nodes."):
            locations["node"] += 1
        elif path.startswith("edges[") or path.startswith("edges."):
            locations["edge"] += 1
        else:
            locations["other"] += 1
    return {key: value for key, value in locations.items() if value}


def _evidence_entry_count(delta: dict[str, Any]) -> int:
    count = 0
    for node in delta.get("nodes", []) or []:
        if isinstance(node, dict):
            count += len(node.get("evidence", []) or [])
    for edge in delta.get("edges", []) or []:
        if isinstance(edge, dict):
            count += len(edge.get("evidence", []) or [])
    return count


def _delta_validation_summary(root: Path, validation: dict[str, Any], delta_path: Path) -> dict[str, Any]:
    target = delta_path if delta_path.is_absolute() else root / delta_path
    target_rel = target.relative_to(root).as_posix()
    row = next((item for item in validation.get("items", []) or [] if item.get("path") == target_rel), None)
    delta = read_json(target, default={}) or {}
    if row is None:
        return {
            "delta_path": target_rel,
            "error_delta": 0,
            "warning_delta": 0,
            "errors": 0,
            "warnings": 0,
            "issue_locations": {},
            "evidence_entries": _evidence_entry_count(delta) if isinstance(delta, dict) else 0,
        }
    errors = int(row.get("errors") or 0)
    warnings = int(row.get("warnings") or 0)
    return {
        "delta_path": target_rel,
        "error_delta": errors,
        "warning_delta": warnings,
        "errors": errors,
        "warnings": warnings,
        "issue_locations": _issue_locations(row.get("issues", []) or []),
        "evidence_entries": _evidence_entry_count(delta) if isinstance(delta, dict) else 0,
    }


def _source_text_for_delta(root: Path, delta: dict[str, Any]) -> str | None:
    paper_index = read_json(root / ".quiver" / "artifacts" / "paper_index.json", default={}) or {}
    paper_paths = {paper.get("id"): paper.get("path") for paper in paper_index.get("papers", []) or []}
    source_rel = paper_paths.get(delta.get("paper_id"))
    if source_rel and (root / source_rel).exists():
        return (root / source_rel).read_text(encoding="utf-8", errors="replace")
    return None


def _validate_single_delta(root: Path, delta_path: Path, *, existing_nodes: set[str] | None = None) -> dict[str, Any]:
    target = delta_path if delta_path.is_absolute() else root / delta_path
    delta = read_json(target, default={}) or {}
    issues = validate_delta(
        delta,
        existing_nodes=existing_nodes or set(),
        source_text=_source_text_for_delta(root, delta) if isinstance(delta, dict) else None,
    )
    return {
        "schema_version": "quiver.validation_report.v1",
        "items": [
            {
                "path": target.relative_to(root).as_posix(),
                "errors": len([issue for issue in issues if issue["severity"] == "error"]),
                "warnings": len([issue for issue in issues if issue["severity"] == "warning"]),
                "issues": issues,
            }
        ],
    }


def _attach_delta_validation(item: dict[str, Any], delta_validation: dict[str, Any]) -> None:
    item["validation_error_delta"] = delta_validation["errors"]
    item["validation_warning_delta"] = delta_validation["warnings"]
    item["validation_delta"] = delta_validation


def _snapshot_file(root: Path, source: Path, dest: Path) -> str | None:
    source = source if source.is_absolute() else root / source
    if not source.exists():
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    return dest.relative_to(root).as_posix()


def run_serial(
    root: Path,
    *,
    paper_ids: list[str] | None = None,
    run: bool = False,
    refresh: bool = False,
    build_site_each: bool = False,
    warn_only: bool = False,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run papers one at a time, rebuilding package context from the current graph.

    The key invariant is that every paper package is built after the previous
    accepted deltas have been merged into ``results/normalized/concept_graph.json``.
    """
    root = require_project(root)
    run_id = run_id or f"serial-{now_stamp()}"
    run_dir = root / "results" / "runs" / run_id
    events_path = run_dir / "events.jsonl"
    if events_path.exists():
        raise ValueError(f"run_id already exists with events log: {run_id}")
    run_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    seq = 0

    def log(event: str, payload: dict[str, Any]) -> None:
        nonlocal seq
        seq += 1
        append_jsonl(
            events_path,
            {
                "seq": seq,
                "ts": now_iso(),
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "event": event,
                "payload": payload,
            },
        )

    index = scan_papers(root)
    selected = paper_ids or [paper["id"] for paper in index.get("papers", [])]
    items: list[dict[str, Any]] = []
    accepted_so_far: list[Path] = []
    log(
        "run_started",
        {
            "run_id": run_id,
            "run": run,
            "refresh": refresh,
            "build_site_each": build_site_each,
            "warn_only": warn_only,
            "paper_ids": selected,
        },
    )

    terminal_status = "completed"
    try:
        for index_i, paper_id in enumerate(selected):
            paper_dir = run_dir / "papers" / paper_id
            current_graph = merge_deltas(root, delta_paths=accepted_so_far)
            pre_graph = {"nodes": len(current_graph.get("nodes", [])), "edges": len(current_graph.get("edges", []))}
            delta_path = root / "results" / "deltas" / f"{paper_id}.json"
            log(
                "paper_started",
                {
                    "paper_id": paper_id,
                    "index": index_i,
                    "pre_graph": pre_graph,
                    "delta_exists": delta_path.exists(),
                    "accepted_so_far": [path.name for path in accepted_so_far],
                },
            )
            if delta_path.exists() and not refresh:
                package_result = build_packages(root, paper_ids=[paper_id], refresh=True)
                package_snapshot = _snapshot_file(root, root / "work" / "packages" / f"{paper_id}.json", paper_dir / "package.json")
                delta_snapshot = _snapshot_file(root, delta_path, paper_dir / "delta.json")
                log("package_built", {"paper_id": paper_id, "result": package_result, "snapshot": package_snapshot})
                existing_nodes = {node.get("id") for node in current_graph.get("nodes", []) or [] if node.get("id")}
                delta_validation = _delta_validation_summary(
                    root,
                    _validate_single_delta(root, delta_path, existing_nodes=existing_nodes),
                    delta_path,
                )
                accepted_so_far.append(delta_path)
                graph = merge_deltas(root, delta_paths=accepted_so_far)
                item = {
                    "paper_id": paper_id,
                    "status": "skipped_existing_delta",
                    "delta_path": delta_path.relative_to(root).as_posix(),
                    "delta_snapshot": delta_snapshot,
                    "nodes": len(graph.get("nodes", [])),
                    "edges": len(graph.get("edges", [])),
                }
                _attach_delta_validation(item, delta_validation)
                if build_site_each:
                    item["site"] = build_site(root)
                items.append(item)
                log("paper_skipped_existing_delta", item)
                continue

            package_result = build_packages(root, paper_ids=[paper_id], refresh=True)
            package_snapshot = _snapshot_file(root, root / "work" / "packages" / f"{paper_id}.json", paper_dir / "package.json")
            log("package_built", {"paper_id": paper_id, "result": package_result, "snapshot": package_snapshot})
            prepared = prepare_extract_requests(root, paper_ids=[paper_id], limit=1)
            item: dict[str, Any] = {"paper_id": paper_id, "status": "prepared", "requests": prepared.get("items", [])}
            for request in prepared.get("items", []):
                request_path = root / request["request_path"]
                request_obj = read_json(request_path, default={}) or {}
                _snapshot_file(root, request_path, paper_dir / "request-pre.json")
                if request_obj.get("prompt_path"):
                    _snapshot_file(root, root / request_obj["prompt_path"], paper_dir / "prompt.md")
            log("extract_prepared", item)

            if run:
                request_paths = [root / request["request_path"] for request in prepared.get("items", [])]
                log("extract_started", {"paper_id": paper_id, "request_paths": [path.relative_to(root).as_posix() for path in request_paths]})
                result = run_prepared_requests(root, request_paths=request_paths)
                for request_path in request_paths:
                    request_obj = read_json(request_path, default={}) or {}
                    _snapshot_file(root, request_path, paper_dir / "request-post.json")
                    if request_obj.get("output_path"):
                        _snapshot_file(root, root / request_obj["output_path"], paper_dir / "last_message.json")
                item["extract"] = result
                log("extract_finished", {"paper_id": paper_id, "result": result})
                statuses = {entry.get("status") for entry in result.get("items", [])}
                if "accepted" in statuses:
                    accepted_delta_path = root / "results" / "deltas" / f"{paper_id}.json"
                    validation_paths = [*accepted_so_far]
                    if accepted_delta_path.exists():
                        validation_paths.append(accepted_delta_path)
                    validation = validate_project(root, delta_paths=validation_paths)
                    errors = sum(entry["errors"] for entry in validation["items"])
                    item["validation_errors"] = errors
                    item["validation_warnings"] = sum(entry["warnings"] for entry in validation["items"])
                    delta_validation = _delta_validation_summary(root, validation, accepted_delta_path)
                    _attach_delta_validation(item, delta_validation)
                    write_json(run_dir / f"validation-after-{paper_id}.json", validation)
                    log(
                        "validation_finished",
                        {
                            "paper_id": paper_id,
                            "errors": item["validation_errors"],
                            "warnings": item["validation_warnings"],
                            "error_delta": item["validation_error_delta"],
                            "warning_delta": item["validation_warning_delta"],
                            "delta_validation": item["validation_delta"],
                            "path": f"validation-after-{paper_id}.json",
                        },
                    )
                    if errors and not warn_only:
                        item["status"] = "validation_failed"
                        items.append(item)
                        terminal_status = "failed"
                        log("paper_failed", item)
                        break
                    if accepted_delta_path.exists():
                        accepted_so_far.append(accepted_delta_path)
                        item["delta_snapshot"] = _snapshot_file(root, accepted_delta_path, paper_dir / "delta.json")
                    graph = merge_deltas(root, delta_paths=accepted_so_far)
                    item["status"] = "accepted_merged"
                    item["nodes"] = len(graph.get("nodes", []))
                    item["edges"] = len(graph.get("edges", []))
                    log("merge_finished", {"paper_id": paper_id, "nodes": item["nodes"], "edges": item["edges"]})
                    if build_site_each:
                        item["site"] = build_site(root)
                else:
                    item["status"] = "extract_failed"
                    items.append(item)
                    terminal_status = "failed"
                    log("paper_failed", item)
                    break

            items.append(item)

        if run and not build_site_each and terminal_status == "completed":
            site_result = build_site(root)
            log("site_built", site_result)
    except BaseException as exc:
        terminal_status = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        payload = {
            "schema_version": "quiver.serial_run.v1",
            "run_id": run_id,
            "run_dir": run_dir.relative_to(root).as_posix(),
            "status": terminal_status,
            "items": items,
            "error": f"{type(exc).__name__}: {exc}",
        }
        write_json(root / ".quiver" / "artifacts" / "last_serial_run.json", payload)
        write_json(run_dir / "summary.json", payload)
        log("run_failed", {"run_id": run_id, "status": terminal_status, "error": payload["error"], "summary": "summary.json"})
        append_event(root, "serial.run", {"count": len(items), "run": run, "refresh": refresh, "status": terminal_status})
        raise

    payload = {
        "schema_version": "quiver.serial_run.v1",
        "run_id": run_id,
        "run_dir": run_dir.relative_to(root).as_posix(),
        "status": terminal_status,
        "items": items,
    }
    write_json(root / ".quiver" / "artifacts" / "last_serial_run.json", payload)
    write_json(run_dir / "summary.json", payload)
    log("run_finished", {"run_id": run_id, "status": terminal_status, "items": len(items), "summary": "summary.json"})
    append_event(root, "serial.run", {"count": len(items), "run": run, "refresh": refresh, "status": terminal_status})
    return payload
