"""Codex request preparation and optional execution."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from quiver.project import append_event, now_iso, read_config, read_json, require_project, write_json
from quiver.prompts import build_extract_prompt
from quiver.validate import validate_delta


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        obj = __import__("json").loads(stripped)
    except Exception:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        obj = __import__("json").loads(stripped[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("Codex output was not a JSON object")
    return obj


def build_codex_command(root: Path, output_path: Path) -> list[str]:
    config = read_config(root)
    codex = config.get("codex", {})
    command = str(codex.get("command") or "codex")
    args = list(codex.get("args") or ["exec", "--json"])
    cmd = [command, *args]
    model = config.get("model")
    if model:
        cmd.extend(["--model", str(model)])
    sandbox = codex.get("sandbox")
    if sandbox:
        cmd.extend(["--sandbox", str(sandbox)])
    schema_path = root / ".quiver" / "schemas" / "graph-delta.schema.json"
    if schema_path.exists():
        cmd.extend(["--output-schema", schema_path.relative_to(root).as_posix()])
    cmd.append("--skip-git-repo-check")
    cmd.extend(["-C", ".", "--output-last-message", output_path.relative_to(root).as_posix(), "-"])
    return cmd


def prepare_extract_requests(
    root: Path, *, limit: int | None = None, paper_ids: list[str] | None = None
) -> dict[str, Any]:
    root = require_project(root)
    worklist = read_json(root / "work" / "packages" / "worklist.json", default={}) or {}
    prepared: list[dict[str, Any]] = []
    packages = worklist.get("packages", []) or []
    wanted = set(paper_ids or [])
    if wanted:
        packages = [item for item in packages if item.get("paper_id") in wanted]
    if limit is not None:
        packages = packages[:limit]

    for item in packages:
        package_path = root / item["path"]
        package = read_json(package_path, default={}) or {}
        paper_id = package.get("paper", {}).get("id") or item["paper_id"]
        attempt_dir = root / "work" / "attempts" / paper_id
        prompt_path = attempt_dir / "prompt.md"
        output_path = attempt_dir / "last_message.json"
        request_path = attempt_dir / "request.json"
        prompt = build_extract_prompt(package)
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt, encoding="utf-8")
        request = {
            "schema_version": "quiver.codex_request.v1",
            "created_at": now_iso(),
            "paper_id": paper_id,
            "package_path": package_path.relative_to(root).as_posix(),
            "prompt_path": prompt_path.relative_to(root).as_posix(),
            "output_path": output_path.relative_to(root).as_posix(),
            "command": build_codex_command(root, output_path),
            "status": "prepared",
        }
        write_json(request_path, request)
        prepared.append({"paper_id": paper_id, "request_path": request_path.relative_to(root).as_posix()})

    append_event(root, "extract.prepare", {"count": len(prepared)})
    return {"schema_version": "quiver.extract_prepare_result.v1", "items": prepared}


def accept_request_output(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    output_path = root / request["output_path"]
    text = output_path.read_text(encoding="utf-8", errors="replace")
    delta = _extract_json_object(text)
    graph = read_json(root / "results" / "normalized" / "concept_graph.json", default={}) or {}
    existing_nodes = {node.get("id") for node in graph.get("nodes", []) or [] if node.get("id")}
    issues = validate_delta(delta, existing_nodes=existing_nodes)
    if request.get("paper_id") and delta.get("paper_id") != request.get("paper_id"):
        issues.append(
            {
                "path": "paper_id",
                "severity": "error",
                "message": f"delta paper_id {delta.get('paper_id')!r} does not match request {request.get('paper_id')!r}",
            }
        )
    errors = [issue for issue in issues if issue["severity"] == "error"]
    if errors:
        request["status"] = "invalid_output"
        request["validation_issues"] = issues
        return {"paper_id": request.get("paper_id"), "status": "invalid_output", "errors": len(errors)}
    paper_id = request.get("paper_id") or delta.get("paper_id")
    delta_path = root / "results" / "deltas" / f"{paper_id}.json"
    write_json(delta_path, delta)
    request["status"] = "accepted"
    request["delta_path"] = delta_path.relative_to(root).as_posix()
    request["validation_issues"] = issues
    return {"paper_id": paper_id, "status": "accepted", "delta_path": request["delta_path"], "warnings": len(issues)}


def run_prepared_requests(
    root: Path, *, limit: int | None = None, request_paths: list[Path] | None = None, timeout_seconds: int | None = None
) -> dict[str, Any]:
    root = require_project(root)
    config = read_config(root)
    if timeout_seconds is None:
        timeout_value = config.get("codex", {}).get("timeout_seconds")
        timeout_seconds = int(timeout_value) if timeout_value else 1200
    request_paths = request_paths or sorted((root / "work" / "attempts").glob("*/request.json"))
    if limit is not None:
        request_paths = request_paths[:limit]
    results: list[dict[str, Any]] = []

    for request_path in request_paths:
        request = read_json(request_path, default={}) or {}
        prompt_path = root / request["prompt_path"]
        prompt = prompt_path.read_text(encoding="utf-8")
        try:
            completed = subprocess.run(
                request["command"],
                input=prompt,
                text=True,
                cwd=root,
                capture_output=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            request["status"] = "timeout"
            request["timeout_seconds"] = timeout_seconds
            request["stdout_tail"] = (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else ""
            request["stderr_tail"] = (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else ""
            write_json(request_path, request)
            results.append({"paper_id": request.get("paper_id"), "status": "timeout", "timeout_seconds": timeout_seconds})
            continue
        request["status"] = "ok" if completed.returncode == 0 else "failed"
        request["returncode"] = completed.returncode
        request["stdout_tail"] = completed.stdout[-2000:]
        request["stderr_tail"] = completed.stderr[-2000:]
        result = {"paper_id": request.get("paper_id"), "status": request["status"], "returncode": completed.returncode}
        if completed.returncode == 0:
            try:
                result = accept_request_output(root, request)
                result["returncode"] = completed.returncode
            except Exception as exc:
                request["status"] = "invalid_output"
                request["error"] = str(exc)
                result = {
                    "paper_id": request.get("paper_id"),
                    "status": "invalid_output",
                    "returncode": completed.returncode,
                    "error": str(exc),
                }
        write_json(request_path, request)
        results.append(result)

    append_event(root, "extract.run", {"count": len(results)})
    return {"schema_version": "quiver.extract_run_result.v1", "items": results}
