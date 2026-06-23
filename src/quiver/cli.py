"""Quiver CLI entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from quiver import __version__
from quiver.audit import audit_run
from quiver.codex import prepare_extract_requests, run_prepared_requests
from quiver.commands.common import echo_json, envelope
from quiver.ingest import scan_papers
from quiver.merge import merge_deltas
from quiver.monitor import monitor_run
from quiver.packages import build_packages
from quiver.project import init_project, require_project, status as project_status
from quiver.search import search_local
from quiver.serial import run_serial
from quiver.site import build_collections_site, build_site
from quiver.validate import validate_project

app = typer.Typer(
    help="Paper-to-concept dependency graph harness.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-V", help="Show version and exit.", callback=_version_callback, is_eager=True
    ),
) -> None:
    """Quiver command line."""


@app.command()
def new(
    path: Path = typer.Argument(Path("."), help="Project directory."),
    force: bool = typer.Option(False, "--force", help="Rewrite Quiver-owned config files."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Create or refresh a Quiver project."""
    result = init_project(path, force=force)
    if json_out:
        echo_json(envelope("quiver.new_result.v1", [result]))
    else:
        typer.echo(f"initialized Quiver project at {result['root']}")


@app.command()
def status(
    path: Path = typer.Argument(Path("."), help="Project directory."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Show project state counts."""
    result = project_status(path)
    if json_out:
        echo_json(envelope("quiver.status.v1", [result]))
    else:
        typer.echo(
            f"{result['papers']} papers, {result['packages']} packages, {result['deltas']} deltas, "
            f"{result['nodes']} nodes, {result['edges']} edges"
        )


@app.command()
def doctor(
    path: Path = typer.Argument(Path("."), help="Project directory."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Check that required project files exist."""
    root = require_project(path)
    checks = [
        ("marker", root / "quiver.toml"),
        ("config", root / ".quiver" / "config.json"),
        ("papers", root / "sources" / "papers"),
        ("registry", root / "registry"),
        ("graph", root / "results" / "normalized" / "concept_graph.json"),
    ]
    items = [{"name": name, "ok": target.exists(), "path": str(target)} for name, target in checks]
    if json_out:
        echo_json(envelope("quiver.doctor.v1", items))
    else:
        for item in items:
            typer.echo(f"{'ok' if item['ok'] else 'missing'} {item['name']}: {item['path']}")


@app.command()
def ingest(
    path: Path = typer.Argument(Path("."), help="Project directory."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Scan markdown papers into a paper index."""
    result = scan_papers(path)
    if json_out:
        echo_json(envelope("quiver.ingest_result.v1", result["papers"]))
    else:
        typer.echo(f"indexed {len(result['papers'])} papers")


@app.command()
def extract(
    path: Path = typer.Argument(Path("."), help="Project directory."),
    run: bool = typer.Option(False, "--run", help="Run Codex after preparing requests."),
    limit: Optional[int] = typer.Option(None, "--limit", help="Limit package count."),
    paper_id: list[str] = typer.Option(None, "--paper-id", help="Paper id to prepare/run. Repeatable."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Prepare Codex extraction prompts; use --run to execute them."""
    root = require_project(path)
    prepared = prepare_extract_requests(root, limit=limit, paper_ids=paper_id)
    request_paths = [root / item["request_path"] for item in prepared["items"]]
    result = run_prepared_requests(root, request_paths=request_paths) if run else prepared
    if json_out:
        echo_json(result)
    else:
        verb = "ran" if run else "prepared"
        typer.echo(f"{verb} {len(result['items'])} extraction requests")


@app.command()
def validate(
    path: Path = typer.Argument(Path("."), help="Project directory."),
    warn_only: bool = typer.Option(False, "--warn-only", help="Do not fail on validation errors."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Validate graph delta files."""
    report = validate_project(path)
    if json_out:
        echo_json(report)
    else:
        errors = sum(item["errors"] for item in report["items"])
        warnings = sum(item["warnings"] for item in report["items"])
        typer.echo(f"validated {len(report['items'])} deltas: {errors} errors, {warnings} warnings")
    errors = sum(item["errors"] for item in report["items"])
    if errors and not warn_only:
        raise typer.Exit(1)


@app.command()
def merge(
    path: Path = typer.Argument(Path("."), help="Project directory."),
    allow_invalid: bool = typer.Option(False, "--allow-invalid", help="Merge even if deltas have validation errors."),
    seed_existing: bool = typer.Option(False, "--seed-existing", help="Seed from current normalized graph instead of clean replay."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Merge graph deltas into the normalized concept graph."""
    try:
        graph = merge_deltas(path, fail_on_error=not allow_invalid, seed_existing=seed_existing)
    except ValueError as exc:
        typer.echo(f"merge failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    item = {"nodes": len(graph["nodes"]), "edges": len(graph["edges"]), "papers": len(graph["papers"])}
    if json_out:
        echo_json(envelope("quiver.merge_result.v1", [item]))
    else:
        typer.echo(f"merged {item['nodes']} nodes and {item['edges']} edges from {item['papers']} papers")


@app.command("build-site")
def build_site_command(
    path: Path = typer.Argument(Path("."), help="Project directory."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Build a static GitHub Pages-ready graph viewer."""
    result = build_site(path)
    if json_out:
        echo_json(envelope("quiver.site_result.v1", [result]))
    else:
        typer.echo(f"wrote static site to {result['path']}")


@app.command("build-collections-site")
def build_collections_site_command(
    output: Path = typer.Argument(..., help="Output directory for the combined static site."),
    project: list[Path] = typer.Argument(..., help="Quiver project directories to include."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Build one static viewer containing multiple concept collections."""
    try:
        result = build_collections_site(output, project)
    except ValueError as exc:
        typer.echo(f"build collections site failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    if json_out:
        echo_json(envelope("quiver.collections_site_result.v1", [result]))
    else:
        typer.echo(f"wrote {result['collections']} collections to {result['path']}")


@app.command("run-serial")
def run_serial_command(
    path: Path = typer.Argument(Path("."), help="Project directory."),
    run: bool = typer.Option(False, "--run", help="Run Codex; otherwise prepare serial requests only."),
    refresh: bool = typer.Option(False, "--refresh", help="Re-run papers even when a delta already exists."),
    paper_id: list[str] = typer.Option(None, "--paper-id", help="Paper id to include. Repeatable."),
    run_id: Optional[str] = typer.Option(None, "--run-id", help="Stable run id for results/runs/<run-id>."),
    build_site_each: bool = typer.Option(False, "--build-site-each", help="Rebuild the static site after every accepted paper."),
    warn_only: bool = typer.Option(False, "--warn-only", help="Continue when validation has warnings/errors."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Run papers one at a time, accumulating the graph after each accepted delta."""
    try:
        result = run_serial(
            path,
            paper_ids=paper_id,
            run=run,
            refresh=refresh,
            build_site_each=build_site_each,
            warn_only=warn_only,
            run_id=run_id,
        )
    except ValueError as exc:
        typer.echo(f"serial run failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    if json_out:
        echo_json(result)
    else:
        for item in result["items"]:
            typer.echo(f"{item['paper_id']}: {item['status']}")


tool_app = typer.Typer(help="Agent-facing deterministic tools.")


@tool_app.command("search")
def tool_search(
    query: str = typer.Argument(..., help="Search query."),
    path: Path = typer.Argument(Path("."), help="Project directory."),
    limit: int = typer.Option(10, "--limit", help="Maximum result count."),
    json_out: bool = typer.Option(True, "--json/--no-json", help="Emit JSON."),
) -> None:
    """Search registry, graph, and paper metadata."""
    root = require_project(path)
    results = search_local(root, query, limit=limit)
    if json_out:
        echo_json(envelope("quiver.search_result.v1", results))
    else:
        for item in results:
            typer.echo(f"{item['score']:.2f} {item['kind']} {item['id']}: {item['label']}")


package_app = typer.Typer(help="Package builder tools.")


@package_app.command("build")
def tool_package_build(
    path: Path = typer.Argument(Path("."), help="Project directory."),
    refresh: bool = typer.Option(False, "--refresh", help="Rewrite existing packages."),
    json_out: bool = typer.Option(True, "--json/--no-json", help="Emit JSON."),
) -> None:
    """Build Codex-ready paper packages."""
    root = require_project(path)
    result = build_packages(root, refresh=refresh)
    if json_out:
        echo_json(result)
    else:
        typer.echo(f"built {len(result['packages'])} packages")


tool_app.add_typer(package_app, name="package")


@tool_app.command("frontier")
def tool_frontier(
    path: Path = typer.Argument(Path("."), help="Project directory."),
    json_out: bool = typer.Option(True, "--json/--no-json", help="Emit JSON."),
) -> None:
    """List merged concepts that need review or one-layer expansion."""
    root = require_project(path)
    from quiver.project import read_json

    graph = read_json(root / "results" / "normalized" / "concept_graph.json", default={}) or {}
    items = [
        {
            "id": node.get("id"),
            "label": node.get("label"),
            "adequacy": node.get("adequacy") or "unknown",
            "paper_ids": node.get("paper_ids", []),
            "summary": node.get("summary") or "",
        }
        for node in graph.get("nodes", []) or []
        if node.get("adequacy") not in (None, "adequate")
    ]
    items.sort(key=lambda item: (item["adequacy"], item["id"] or ""))
    if json_out:
        echo_json(envelope("quiver.frontier.v1", items))
    else:
        for item in items:
            typer.echo(f"{item['adequacy']} {item['id']}: {item['label']}")


@tool_app.command("audit-run")
def tool_audit_run(
    run_id: str = typer.Argument(..., help="Run id under results/runs/."),
    path: Path = typer.Argument(Path("."), help="Project directory."),
    similar_threshold: float = typer.Option(0.86, "--similar-threshold", help="Near-duplicate candidate threshold."),
    similar_limit: int = typer.Option(50, "--similar-limit", help="Maximum near-duplicate candidates."),
    no_write: bool = typer.Option(False, "--no-write", help="Do not write results/runs/<run-id>/audit.json."),
    json_out: bool = typer.Option(True, "--json/--no-json", help="Emit JSON."),
) -> None:
    """Summarize a serial run's durable logs, validation reports, and graph risks."""
    result = audit_run(path, run_id, similar_threshold=similar_threshold, similar_limit=similar_limit, write=not no_write)
    if json_out:
        echo_json(envelope("quiver.run_audit.v1", [result]))
    else:
        graph = result["graph"]
        validation = result["validation"]
        typer.echo(
            f"{result['status']} run {run_id}: {graph['papers']} papers, {graph['nodes']} nodes, "
            f"{graph['edges']} edges, {validation['latest']['warnings'] if validation['latest'] else 0} latest warnings"
        )


@tool_app.command("monitor-run")
def tool_monitor_run(
    run_id: str = typer.Argument(..., help="Run id under results/runs/."),
    path: Path = typer.Argument(Path("."), help="Project directory."),
    append: bool = typer.Option(False, "--append", help="Append to results/runs/<run-id>/monitor.jsonl."),
    output_path: Optional[Path] = typer.Option(None, "--output-path", help="Optional JSONL path for --append."),
    json_out: bool = typer.Option(True, "--json/--no-json", help="Emit JSON."),
) -> None:
    """Read cheap in-run status without a full graph audit."""
    try:
        result = monitor_run(path, run_id, append=append, output_path=output_path)
    except FileNotFoundError as exc:
        typer.echo(f"monitor failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    if json_out:
        echo_json(envelope("quiver.run_monitor.v1", [result]))
    else:
        active = result.get("active_paper") or {}
        active_text = active.get("paper_id") or result.get("last_paper") or "-"
        graph = result["graph"]
        validation = result["validation"]
        typer.echo(
            f"{result['status']} run {run_id}: {result['event_count']} events, paper {active_text}, "
            f"{graph['papers']} papers, {graph['nodes']} nodes, {graph['edges']} edges, "
            f"{validation.get('latest_warnings', validation.get('warnings', 0))} latest paper warnings "
            f"(+{validation.get('warning_delta', 0)})"
        )


app.add_typer(tool_app, name="tool")


if __name__ == "__main__":
    app()
