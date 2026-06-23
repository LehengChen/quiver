from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from quiver.cli import app
from quiver.project import append_jsonl, write_json


def test_cli_new_status_json(tmp_path: Path) -> None:
    runner = CliRunner()
    root = tmp_path / "demo"
    result = runner.invoke(app, ["new", str(root), "--json"])
    assert result.exit_code == 0, result.output
    assert "quiver.new_result.v1" in result.output

    result = runner.invoke(app, ["status", str(root), "--json"])
    assert result.exit_code == 0, result.output
    assert "quiver.status.v1" in result.output


def test_cli_doctor(tmp_path: Path) -> None:
    runner = CliRunner()
    root = tmp_path / "demo"
    assert runner.invoke(app, ["new", str(root)]).exit_code == 0
    result = runner.invoke(app, ["doctor", str(root), "--json"])
    assert result.exit_code == 0, result.output
    assert '"ok": true' in result.output


def test_cli_validate_fails_on_invalid_delta(tmp_path: Path) -> None:
    runner = CliRunner()
    root = tmp_path / "demo"
    assert runner.invoke(app, ["new", str(root)]).exit_code == 0
    write_json(
        root / "results" / "deltas" / "bad.json",
        {"schema_version": "quiver.graph_delta.v1", "paper_id": "bad", "nodes": [], "edges": [{"dependent": "missing"}]},
    )
    result = runner.invoke(app, ["validate", str(root)])
    assert result.exit_code == 1


def test_cli_extract_can_filter_paper_id(tmp_path: Path) -> None:
    runner = CliRunner()
    root = tmp_path / "demo"
    assert runner.invoke(app, ["new", str(root)]).exit_code == 0
    papers = root / "sources" / "papers"
    (papers / "a.md").write_text("# Alpha\n\nAlpha concept.", encoding="utf-8")
    (papers / "b.md").write_text("# Beta\n\nBeta concept.", encoding="utf-8")
    assert runner.invoke(app, ["ingest", str(root)]).exit_code == 0
    assert runner.invoke(app, ["tool", "package", "build", str(root)]).exit_code == 0
    result = runner.invoke(app, ["extract", str(root), "--paper-id", "b", "--json"])
    assert result.exit_code == 0, result.output
    assert '"paper_id": "b"' in result.output
    assert '"paper_id": "a"' not in result.output


def test_cli_run_serial_prepare(tmp_path: Path) -> None:
    runner = CliRunner()
    root = tmp_path / "demo"
    assert runner.invoke(app, ["new", str(root)]).exit_code == 0
    (root / "sources" / "papers" / "a.md").write_text("# Alpha\n\nAlpha concept.", encoding="utf-8")
    result = runner.invoke(app, ["run-serial", str(root), "--json"])
    assert result.exit_code == 0, result.output
    assert "quiver.serial_run.v1" in result.output
    assert '"status": "prepared"' in result.output


def test_cli_frontier_lists_non_adequate_nodes(tmp_path: Path) -> None:
    runner = CliRunner()
    root = tmp_path / "demo"
    assert runner.invoke(app, ["new", str(root)]).exit_code == 0
    write_json(
        root / "results" / "normalized" / "concept_graph.json",
        {
            "schema_version": "quiver.graph.v1",
            "dataset": {"id": "demo", "title": "demo"},
            "papers": [],
            "nodes": [
                {"id": "known", "label": "Known", "adequacy": "adequate"},
                {"id": "frontier", "label": "Frontier", "adequacy": "needs_one_layer"},
            ],
            "edges": [],
        },
    )
    result = runner.invoke(app, ["tool", "frontier", str(root), "--json"])
    assert result.exit_code == 0, result.output
    assert "frontier" in result.output
    assert "known" not in result.output


def test_cli_monitor_run_json_append(tmp_path: Path) -> None:
    runner = CliRunner()
    root = tmp_path / "demo"
    assert runner.invoke(app, ["new", str(root)]).exit_code == 0
    run_dir = root / "results" / "runs" / "run-1"
    append_jsonl(run_dir / "events.jsonl", {"seq": 1, "event": "run_started", "elapsed_seconds": 0, "payload": {"paper_ids": ["alpha"]}})
    append_jsonl(run_dir / "events.jsonl", {"seq": 2, "event": "paper_started", "elapsed_seconds": 1, "payload": {"paper_id": "alpha", "index": 0}})

    result = runner.invoke(app, ["tool", "monitor-run", "run-1", str(root), "--append", "--json"])
    assert result.exit_code == 0, result.output
    assert "quiver.run_monitor.v1" in result.output
    assert '"status": "running"' in result.output
    assert (run_dir / "monitor.jsonl").exists()
