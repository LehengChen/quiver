from __future__ import annotations

import shutil
import sys
from pathlib import Path

from quiver import site as site_module
from quiver.audit import audit_run
from quiver.codex import run_prepared_requests
from quiver.ingest import scan_papers
from quiver.merge import merge_deltas
from quiver.monitor import monitor_run
from quiver.packages import build_packages
from quiver.project import append_jsonl, init_project, read_json, read_jsonl, status, write_json
from quiver.search import search_local
from quiver.serial import run_serial
from quiver.site import build_site
from quiver.site_data import build_site_payloads
from quiver.validate import validate_project


FIXTURE = Path(__file__).parent / "projects" / "minimal-md-batch"


def copy_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "minimal-md-batch"
    shutil.copytree(FIXTURE, root)
    return root


def test_ingest_package_search_extract_merge_site(tmp_path: Path) -> None:
    root = copy_fixture(tmp_path)
    index = scan_papers(root)
    assert len(index["papers"]) == 1

    worklist = build_packages(root, refresh=True)
    assert len(worklist["packages"]) == 1
    package = read_json(root / worklist["packages"][0]["path"])
    assert package["paper"]["id"] == "quiver-representations"
    assert package["local_search_results"]

    delta = {
        "schema_version": "quiver.graph_delta.v1",
        "paper_id": "quiver-representations",
        "paper_title": "Quiver Representations",
        "nodes": [
            {
                "canonical_id": "quiver",
                "label": "Quiver",
                "entity_type": "object",
                "ontology_status": "existing",
                "local_role": "supporting",
                "aliases": ["directed graph"],
                "summary": "A directed graph.",
                "evidence": [{"quote": "A quiver is a directed graph.", "section": ""}],
                "confidence": "high",
                "adequacy": "adequate",
            },
            {
                "canonical_id": "quiver_representation",
                "label": "Quiver representation",
                "entity_type": "definition",
                "ontology_status": "new",
                "local_role": "main",
                "aliases": [],
                "summary": "An assignment of vector spaces to vertices and linear maps to arrows.",
                "evidence": [{"quote": "assigns a vector space to each vertex and a linear map to each arrow", "section": ""}],
                "confidence": "high",
                "adequacy": "adequate",
            },
        ],
        "edges": [
            {
                "dependent": "quiver_representation",
                "prerequisite": "quiver",
                "relation": "definition_depends_on",
                "evidence": [{"quote": "representation of a quiver", "section": ""}],
                "confidence": "high",
            }
        ],
        "notes": [],
    }
    (root / "results" / "deltas" / "quiver-representations.json").write_text(
        __import__("json").dumps(delta, indent=2), encoding="utf-8"
    )

    report = validate_project(root)
    assert report["items"][0]["errors"] == 0
    graph = merge_deltas(root)
    assert len(graph["nodes"]) == 2
    assert graph["edges"][0]["dependent"] == "quiver_representation"
    assert graph["edges"][0]["prerequisite"] == "quiver"

    results = search_local(root, "representation", limit=5)
    assert any(item["id"] == "quiver_representation" for item in results)

    site = build_site(root)
    site_dir = root / site["path"]
    assert {"index.html", "graph.json", "analysis.json", "manifest.json"}.issubset(set(site["files"]))
    assert site["frontend"] in {"react", "fallback"}
    assert (root / site["path"] / "index.html").exists()
    assert (site_dir / "graph.json").exists()
    assert (site_dir / "analysis.json").exists()
    assert (site_dir / "manifest.json").exists()
    exported_graph = read_json(site_dir / "graph.json")
    analysis = read_json(site_dir / "analysis.json")
    manifest = read_json(site_dir / "manifest.json")
    assert exported_graph["nodes"][1]["id"] == "quiver_representation"
    assert exported_graph["validation"][0]["paper_id"] == "quiver-representations"
    assert analysis["summary"]["concepts"] == 2
    assert analysis["summary"]["dependencies"] == 1
    assert analysis["paper_summaries"][0]["concepts"] == 2
    assert analysis["paper_summaries"][0]["unique_concepts"] == 2
    assert analysis["relation_groups"]["strict_dependency"] == ["definition_depends_on"]
    assert manifest["source_graph"] == "results/normalized/concept_graph.json"
    assert status(root)["nodes"] == 2


def test_paper_metadata_sidecar_is_publicly_sanitized(tmp_path: Path) -> None:
    root = tmp_path / "metadata-demo"
    init_project(root)
    (root / "sources" / "papers" / "MR1234567.md").write_text("# Placeholder Title\n\nA concept.", encoding="utf-8")
    append_jsonl(
        root / "sources" / "paper_metadata.jsonl",
        {
            "paper_id": "MR1234567",
            "title": "Metadata Title",
            "authors": ["Doe, Jane"],
            "journal": "Invent. Math.",
            "year": 2024,
            "primary_msc": "53C21",
            "primary_msc_description": "Riemannian geometry",
            "doi": "10.0000/example",
            "source_local_path": "/not/public/MR1234567.md",
        },
    )
    index = scan_papers(root)
    paper = index["papers"][0]
    assert paper["id"] == "mr1234567"
    assert paper["title"] == "Metadata Title"
    assert paper["journal"] == "Invent. Math."
    assert "source_local_path" not in paper

    write_json(
        root / "results" / "deltas" / "mr1234567.json",
        {
            "schema_version": "quiver.graph_delta.v1",
            "paper_id": "mr1234567",
            "paper_title": "Metadata Title",
            "nodes": [],
            "edges": [],
            "notes": [],
        },
    )
    graph = merge_deltas(root)
    assert graph["papers"][0]["authors"] == ["Doe, Jane"]
    assert graph["papers"][0]["primary_msc"] == "53C21"
    assert "path" not in graph["papers"][0]
    assert "sha256" not in graph["papers"][0]


def test_site_analysis_warning_counts_are_self_contained(tmp_path: Path) -> None:
    root = tmp_path / "site-analysis"
    init_project(root)
    write_json(
        root / "results" / "normalized" / "concept_graph.json",
        {
            "schema_version": "quiver.graph.v1",
            "dataset": {"id": "site-analysis", "title": "Site Analysis"},
            "papers": [{"id": "paper-one", "title": "Paper One"}],
            "nodes": [],
            "edges": [],
            "validation": [{"path": "results/deltas/not-the-paper-id.json", "paper_id": "paper-one", "errors": 0, "warnings": 7}],
        },
    )

    _, analysis, _ = build_site_payloads(root)

    assert analysis["summary"]["evidence_warnings"] == 7
    assert analysis["paper_summaries"][0]["evidence_warnings"] == 7


def test_build_site_copies_existing_react_dist_and_manifest_files(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "site-demo"
    init_project(root)
    write_json(
        root / "results" / "normalized" / "concept_graph.json",
        {
            "schema_version": "quiver.graph.v1",
            "dataset": {"id": "site-demo", "title": "Site Demo"},
            "papers": [],
            "nodes": [],
            "edges": [],
            "validation": [],
        },
    )
    repo = tmp_path / "repo"
    assets = repo / "web" / "dist" / "assets"
    assets.mkdir(parents=True)
    (repo / "web" / "dist" / "index.html").write_text('<script type="module" src="./assets/app.js"></script>', encoding="utf-8")
    (assets / "app.js").write_text("console.log('quiver');", encoding="utf-8")
    monkeypatch.setattr(site_module, "_repo_root", lambda: repo)

    result = site_module.build_site(root)

    site_dir = root / result["path"]
    manifest = read_json(site_dir / "manifest.json")
    assert result["frontend"] == "react"
    assert "assets/app.js" in result["files"]
    assert (site_dir / "assets" / "app.js").exists()
    assert manifest["frontend"] == "react"
    assert manifest["build_source"] == "existing_dist"
    assert "assets/app.js" in manifest["files"]


def test_build_collections_site_exports_collection_index(tmp_path: Path, monkeypatch) -> None:
    roots = []
    for name in ["algebraic-geometry", "homotopy-theory"]:
        root = tmp_path / name
        init_project(root)
        write_json(
            root / "results" / "normalized" / "concept_graph.json",
            {
                "schema_version": "quiver.graph.v1",
                "dataset": {"id": name, "title": name.replace("-", " ").title()},
                "papers": [],
                "nodes": [],
                "edges": [],
                "validation": [],
            },
        )
        roots.append(root)

    repo = tmp_path / "repo"
    assets = repo / "web" / "dist" / "assets"
    assets.mkdir(parents=True)
    (repo / "web" / "dist" / "index.html").write_text('<script type="module" src="./assets/app.js"></script>', encoding="utf-8")
    (assets / "app.js").write_text("console.log('quiver');", encoding="utf-8")
    monkeypatch.setattr(site_module, "_repo_root", lambda: repo)

    result = site_module.build_collections_site(tmp_path / "combined-site", roots)
    site_dir = Path(result["path"])
    collections = read_json(site_dir / "collections.json")
    manifest = read_json(site_dir / "manifest.json")

    assert result["collections"] == 2
    assert collections["schema_version"] == "quiver.site_collections.v1"
    assert [item["id"] for item in collections["collections"]] == ["algebraic-geometry", "homotopy-theory"]
    assert (site_dir / "collections" / "algebraic-geometry" / "graph.json").exists()
    assert (site_dir / "collections" / "homotopy-theory" / "analysis.json").exists()
    assert manifest["collection_count"] == 2
    assert "collections.json" in manifest["files"]


def test_ingest_skips_image_only_title_lines(tmp_path: Path) -> None:
    root = tmp_path / "image-title"
    init_project(root)
    (root / "sources" / "papers" / "paper.md").write_text(
        "# ![](images/cover.jpg)\n\n# Actual Mathematical Title\n\nBody.",
        encoding="utf-8",
    )

    index = scan_papers(root)
    assert index["papers"][0]["title"] == "Actual Mathematical Title"


def test_merge_clean_replay_removes_deleted_delta(tmp_path: Path) -> None:
    root = copy_fixture(tmp_path)
    delta_path = root / "results" / "deltas" / "one.json"
    write_json(
        delta_path,
        {
            "schema_version": "quiver.graph_delta.v1",
            "paper_id": "one",
            "paper_title": "One",
            "nodes": [
                {
                    "canonical_id": "quiver",
                    "label": "Quiver",
                    "entity_type": "object",
                    "ontology_status": "existing",
                    "local_role": "main",
                    "aliases": [],
                    "summary": "A directed graph.",
                    "evidence": [{"quote": "A quiver is a directed graph.", "section": ""}],
                    "confidence": "high",
                    "adequacy": "adequate",
                }
            ],
            "edges": [],
            "notes": [],
        },
    )
    assert len(merge_deltas(root)["nodes"]) == 1
    delta_path.unlink()
    assert len(merge_deltas(root)["nodes"]) == 0


def test_run_prepared_request_accepts_delta_output(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    init_project(root)
    attempt_dir = root / "work" / "attempts" / "paper-one"
    attempt_dir.mkdir(parents=True)
    prompt_path = attempt_dir / "prompt.md"
    output_path = attempt_dir / "last_message.json"
    source_delta = attempt_dir / "source_delta.json"
    request_path = attempt_dir / "request.json"
    prompt_path.write_text("prompt", encoding="utf-8")
    write_json(
        source_delta,
        {
            "schema_version": "quiver.graph_delta.v1",
            "paper_id": "paper-one",
            "paper_title": "Paper One",
            "nodes": [
                {
                    "canonical_id": "quiver",
                    "label": "Quiver",
                    "entity_type": "object",
                    "ontology_status": "existing",
                    "local_role": "main",
                    "aliases": [],
                    "summary": "A directed graph.",
                    "evidence": [{"quote": "A quiver is a directed graph.", "section": ""}],
                    "confidence": "high",
                    "adequacy": "adequate",
                }
            ],
            "edges": [],
            "notes": [],
        },
    )
    write_json(
        request_path,
        {
            "schema_version": "quiver.codex_request.v1",
            "paper_id": "paper-one",
            "prompt_path": prompt_path.relative_to(root).as_posix(),
            "output_path": output_path.relative_to(root).as_posix(),
            "command": [
                sys.executable,
                "-c",
                "import shutil,sys; shutil.copyfile(sys.argv[1], sys.argv[2])",
                str(source_delta),
                str(output_path),
            ],
            "status": "prepared",
        },
    )
    result = run_prepared_requests(root, request_paths=[request_path])
    assert result["items"][0]["status"] == "accepted"
    assert (root / "results" / "deltas" / "paper-one.json").exists()


def test_run_prepared_request_rejects_wrong_paper_id(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    init_project(root)
    attempt_dir = root / "work" / "attempts" / "paper-one"
    attempt_dir.mkdir(parents=True)
    prompt_path = attempt_dir / "prompt.md"
    output_path = attempt_dir / "last_message.json"
    source_delta = attempt_dir / "source_delta.json"
    request_path = attempt_dir / "request.json"
    prompt_path.write_text("prompt", encoding="utf-8")
    write_json(
        source_delta,
        {
            "schema_version": "quiver.graph_delta.v1",
            "paper_id": "wrong-paper",
            "paper_title": "Wrong Paper",
            "nodes": [],
            "edges": [],
            "notes": [],
        },
    )
    write_json(
        request_path,
        {
            "schema_version": "quiver.codex_request.v1",
            "paper_id": "paper-one",
            "prompt_path": prompt_path.relative_to(root).as_posix(),
            "output_path": output_path.relative_to(root).as_posix(),
            "command": [
                sys.executable,
                "-c",
                "import shutil,sys; shutil.copyfile(sys.argv[1], sys.argv[2])",
                str(source_delta),
                str(output_path),
            ],
            "status": "prepared",
        },
    )
    result = run_prepared_requests(root, request_paths=[request_path])
    assert result["items"][0]["status"] == "invalid_output"
    assert not (root / "results" / "deltas" / "paper-one.json").exists()


def test_serial_runner_rebuilds_context_from_accumulated_graph(tmp_path: Path) -> None:
    root = tmp_path / "serial-demo"
    init_project(root)
    (root / "sources" / "papers" / "alpha.md").write_text("# Alpha\n\nA quiver is a directed graph.", encoding="utf-8")
    (root / "sources" / "papers" / "beta.md").write_text(
        "# Beta\n\nA quiver representation assigns vector spaces to vertices.", encoding="utf-8"
    )
    helper = root / "fake_codex.py"
    helper.write_text(
        """
import json
import sys
from pathlib import Path

prompt = sys.stdin.read()
out = Path(sys.argv[sys.argv.index("--output-last-message") + 1])
paper_id = "beta" if '"paper_id": "beta"' in prompt else "alpha"
if paper_id == "alpha":
    delta = {
        "schema_version": "quiver.graph_delta.v1",
        "paper_id": "alpha",
        "paper_title": "Alpha",
        "nodes": [{
            "canonical_id": "quiver",
            "label": "Quiver",
            "entity_type": "object",
            "ontology_status": "new",
            "local_role": "main",
            "aliases": [],
            "summary": "A directed graph.",
            "evidence": [{"quote": "A quiver is a directed graph.", "section": ""}],
            "confidence": "high",
            "adequacy": "adequate",
        }],
        "edges": [],
        "notes": [],
    }
else:
    delta = {
        "schema_version": "quiver.graph_delta.v1",
        "paper_id": "beta",
        "paper_title": "Beta",
        "nodes": [
            {
                "canonical_id": "quiver",
                "label": "Quiver",
                "entity_type": "object",
                "ontology_status": "existing",
                "local_role": "supporting",
                "aliases": [],
                "summary": "A directed graph.",
                "evidence": [{"quote": "quiver", "section": ""}],
                "confidence": "high",
                "adequacy": "adequate",
            },
            {
                "canonical_id": "quiver_representation",
                "label": "Quiver representation",
                "entity_type": "definition",
                "ontology_status": "new",
                "local_role": "main",
                "aliases": [],
                "summary": "An assignment of vector spaces to vertices.",
                "evidence": [{"quote": "assigns vector spaces to vertices", "section": ""}],
                "confidence": "high",
                "adequacy": "adequate",
            },
        ],
        "edges": [{
            "dependent": "quiver_representation",
            "prerequisite": "quiver",
            "relation": "definition_depends_on",
            "evidence": [{"quote": "this exact edge quote is absent", "section": ""}],
            "confidence": "high",
        }],
        "notes": [],
    }
out.write_text(json.dumps(delta), encoding="utf-8")
""",
        encoding="utf-8",
    )
    config = read_json(root / ".quiver" / "config.json")
    config["codex"]["command"] = sys.executable
    config["codex"]["args"] = [str(helper)]
    config["codex"]["sandbox"] = ""
    write_json(root / ".quiver" / "config.json", config)

    result = run_serial(root, run=True, run_id="test-serial")
    assert [item["status"] for item in result["items"]] == ["accepted_merged", "accepted_merged"]
    assert result["items"][0]["validation_warning_delta"] == 0
    assert result["items"][1]["validation_warning_delta"] == 1
    assert result["items"][1]["validation_error_delta"] == 0
    assert result["items"][1]["validation_delta"]["warning_delta"] == 1
    assert result["items"][1]["validation_delta"]["issue_locations"] == {"edge": 1}
    assert result["items"][1]["validation_delta"]["evidence_entries"] == 3
    assert result["run_dir"] == "results/runs/test-serial"
    events = (root / "results" / "runs" / "test-serial" / "events.jsonl").read_text(encoding="utf-8")
    assert "run_started" in events
    assert "merge_finished" in events
    assert '"seq":' in events
    assert '"ts":' in events
    assert (root / "results" / "runs" / "test-serial" / "summary.json").exists()
    try:
        run_serial(root, run=False, run_id="test-serial")
    except ValueError as exc:
        assert "run_id already exists" in str(exc)
    else:
        raise AssertionError("expected run_id collision to fail")
    graph = read_json(root / "results" / "normalized" / "concept_graph.json")
    assert len(graph["papers"]) == 2
    assert {node["id"] for node in graph["nodes"]} == {"quiver", "quiver_representation"}
    audit = audit_run(root, "test-serial")
    assert audit["status"] == "completed"
    assert audit["event_count"] >= 1
    assert audit["graph"]["nodes"] == 2
    assert audit["graph"]["frontier"]["count"] == 0
    assert audit["papers"][1]["extract_seconds"] >= 0
    assert audit["papers"][1]["validation_warning_delta"] == 1
    assert audit["papers"][1]["validation_delta"]["issue_locations"] == {"edge": 1}
    assert audit["artifacts"][1]["has_response_snapshot"] is True
    assert (root / "results" / "runs" / "test-serial" / "audit.json").exists()

    beta_package = read_json(root / "work" / "packages" / "beta.json")
    assert beta_package["existing_graph_summary"]["nodes"] == 1
    assert beta_package["allowed_existing_nodes"][0]["id"] == "quiver"


def test_serial_runner_does_not_leak_future_existing_deltas(tmp_path: Path) -> None:
    root = tmp_path / "serial-demo"
    init_project(root)
    (root / "sources" / "papers" / "alpha.md").write_text("# Alpha\n\nAlpha concept.", encoding="utf-8")
    (root / "sources" / "papers" / "beta.md").write_text("# Beta\n\nBeta concept.", encoding="utf-8")
    write_json(
        root / "results" / "deltas" / "beta.json",
        {
            "schema_version": "quiver.graph_delta.v1",
            "paper_id": "beta",
            "paper_title": "Beta",
            "nodes": [
                {
                    "canonical_id": "beta_concept",
                    "label": "Beta concept",
                    "entity_type": "definition",
                    "ontology_status": "new",
                    "local_role": "main",
                    "aliases": [],
                    "summary": "A concept from beta.",
                    "evidence": [{"quote": "Beta concept.", "section": ""}],
                    "confidence": "high",
                    "adequacy": "adequate",
                }
            ],
            "edges": [],
            "notes": [],
        },
    )

    result = run_serial(root, run=False, run_id="future-delta")
    assert [item["status"] for item in result["items"]] == ["prepared", "skipped_existing_delta"]
    assert result["items"][1]["validation_warning_delta"] == 0
    assert result["items"][1]["validation_error_delta"] == 0
    alpha_package = read_json(root / "work" / "packages" / "alpha.json")
    assert alpha_package["existing_graph_summary"]["nodes"] == 0
    graph = read_json(root / "results" / "normalized" / "concept_graph.json")
    assert [node["id"] for node in graph["nodes"]] == ["beta_concept"]


def test_monitor_run_reports_running_before_summary(tmp_path: Path) -> None:
    root = tmp_path / "monitor-demo"
    init_project(root)
    write_json(
        root / "results" / "normalized" / "concept_graph.json",
        {
            "schema_version": "quiver.graph.v1",
            "dataset": {"id": "monitor-demo", "title": "monitor-demo"},
            "papers": [{"id": "alpha"}],
            "nodes": [{"id": "alpha_concept"}],
            "edges": [],
        },
    )
    run_dir = root / "results" / "runs" / "run-1"
    append_jsonl(run_dir / "events.jsonl", {"seq": 1, "event": "run_started", "elapsed_seconds": 0, "payload": {"paper_ids": ["alpha", "beta"]}})
    append_jsonl(run_dir / "events.jsonl", {"seq": 2, "event": "paper_started", "elapsed_seconds": 1, "payload": {"paper_id": "alpha", "index": 0}})
    append_jsonl(run_dir / "events.jsonl", {"seq": 3, "event": "extract_started", "elapsed_seconds": 2, "payload": {"paper_id": "alpha"}})

    sample = monitor_run(root, "run-1")
    assert sample["status"] == "running"
    assert sample["active_paper"]["paper_id"] == "alpha"
    assert sample["active_paper"]["phase"] == "extracting"
    assert sample["last_event"] == "extract_started"
    assert sample["progress"] == {"completed": 0, "total": 2}
    assert sample["graph"] == {"path": "results/normalized/concept_graph.json", "papers": 1, "nodes": 1, "edges": 0}
    assert not (run_dir / "audit.json").exists()
    assert "review_queue" not in sample["graph"]
    assert "similar_candidates" not in sample["graph"]


def test_monitor_run_reads_latest_validation_and_appends_jsonl(tmp_path: Path) -> None:
    root = tmp_path / "monitor-demo"
    init_project(root)
    run_dir = root / "results" / "runs" / "run-1"
    write_json(
        root / "results" / "deltas" / "alpha.json",
        {
            "schema_version": "quiver.graph_delta.v1",
            "paper_id": "alpha",
            "paper_title": "Alpha",
            "nodes": [
                {
                    "canonical_id": "alpha_concept",
                    "label": "Alpha concept",
                    "entity_type": "definition",
                    "ontology_status": "new",
                    "local_role": "main",
                    "aliases": [],
                    "summary": "Alpha.",
                    "evidence": [{"quote": "Alpha", "section": ""}],
                    "confidence": "high",
                    "adequacy": "adequate",
                }
            ],
            "edges": [],
            "notes": [],
        },
    )
    write_json(
        run_dir / "validation-after-alpha.json",
        {
            "schema_version": "quiver.validation_report.v1",
            "items": [
                {
                    "path": "results/deltas/alpha.json",
                    "errors": 0,
                    "warnings": 1,
                    "issues": [{"path": "nodes[0].evidence[0].quote", "severity": "warning", "message": "missing"}],
                }
            ],
        },
    )
    append_jsonl(run_dir / "events.jsonl", {"seq": 1, "event": "run_started", "elapsed_seconds": 0, "payload": {"paper_ids": ["alpha"]}})
    append_jsonl(run_dir / "events.jsonl", {"seq": 2, "event": "paper_started", "elapsed_seconds": 1, "payload": {"paper_id": "alpha", "index": 0}})
    append_jsonl(
        run_dir / "events.jsonl",
        {
            "seq": 3,
            "event": "validation_finished",
            "elapsed_seconds": 2,
            "payload": {"paper_id": "alpha", "errors": 0, "warnings": 1, "path": "validation-after-alpha.json"},
        },
    )

    first = monitor_run(root, "run-1", append=True)
    second = monitor_run(root, "run-1", append=True)
    rows = read_jsonl(run_dir / "monitor.jsonl")
    assert first["sample_id"] == "sample-001"
    assert second["sample_id"] == "sample-002"
    assert len(rows) == 2
    assert second["validation"]["latest_path"] == "results/runs/run-1/validation-after-alpha.json"
    assert second["validation"]["latest_warnings"] == 1
    assert second["validation"]["warning_delta"] == 1
    assert second["validation"]["delta_validation"]["issue_locations"] == {"node": 1}
    assert second["validation"]["delta_validation"]["evidence_entries"] == 1
