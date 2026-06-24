from __future__ import annotations

from pathlib import Path

from quiver.project import init_project, write_json
from quiver.search import search_local
from quiver.validate import validate_delta


def _node(**overrides):
    node = {
        "canonical_id": "valid_concept",
        "label": "Valid concept",
        "entity_type": "object",
        "ontology_status": "new",
        "local_role": "main",
        "aliases": [],
        "summary": "A reusable mathematical concept.",
        "evidence": [{"quote": "Valid concept", "section": ""}],
        "confidence": "high",
        "adequacy": "adequate",
    }
    node.update(overrides)
    return node


def test_validate_delta_rejects_theorem_node_type() -> None:
    delta = {
        "schema_version": "quiver.graph_delta.v1",
        "paper_id": "paper",
        "paper_title": "Paper",
        "nodes": [_node(canonical_id="local_theorem", label="Local theorem", entity_type="theorem")],
        "edges": [],
        "notes": [],
    }

    issues = validate_delta(delta)

    assert any(issue["severity"] == "error" and "invalid entity_type" in issue["message"] for issue in issues)
    assert any(issue["severity"] == "error" and "theorem nodes are not part" in issue["message"] for issue in issues)


def test_validate_delta_rejects_numbered_result_node_identity() -> None:
    delta = {
        "schema_version": "quiver.graph_delta.v1",
        "paper_id": "paper",
        "paper_title": "Paper",
        "nodes": [
            _node(
                canonical_id="corrected_lemma_2_40_forest_condition",
                label="Corrected Lemma 2.40 forest condition",
                aliases=["Lemma 2.40"],
            )
        ],
        "edges": [],
        "notes": [],
    }

    issues = validate_delta(delta)

    assert any(issue["severity"] == "error" and "paper-local numbered" in issue["message"] for issue in issues)


def test_validate_delta_allows_named_conjecture_with_dimension() -> None:
    delta = {
        "schema_version": "quiver.graph_delta.v1",
        "paper_id": "paper",
        "paper_title": "Paper",
        "nodes": [
            _node(
                canonical_id="generalized_smale_conjecture_3_manifolds",
                label="Generalized Smale Conjecture for 3-manifolds",
            )
        ],
        "edges": [],
        "notes": [],
    }

    issues = validate_delta(delta)

    assert not any(issue["severity"] == "error" and "paper-local numbered" in issue["message"] for issue in issues)


def test_validate_delta_rejects_appendix_and_roman_result_node_ids() -> None:
    for canonical_id in [
        "lemma_2_regular_case",
        "lemma_2_1a_regular_case",
        "theorem_a_1b_extension",
        "proposition_ii_3b_boundary_case",
    ]:
        delta = {
            "schema_version": "quiver.graph_delta.v1",
            "paper_id": "paper",
            "paper_title": "Paper",
            "nodes": [_node(canonical_id=canonical_id, label="Reusable concept")],
            "edges": [],
            "notes": [],
        }

        issues = validate_delta(delta)

        assert any(issue["severity"] == "error" and "paper-local numbered" in issue["message"] for issue in issues)


def test_search_filters_existing_numbered_result_nodes(tmp_path: Path) -> None:
    root = tmp_path / "search-quality"
    init_project(root)
    write_json(
        root / "results" / "normalized" / "concept_graph.json",
        {
            "schema_version": "quiver.graph.v1",
            "dataset": {"id": "search-quality", "title": "Search Quality"},
            "papers": [],
            "nodes": [
                {
                    "id": "theorem_2_1_representation_growth",
                    "label": "Theorem 2.1 of Representation Growth",
                    "entity_type": "theorem",
                    "aliases": ["Theorem 2.1"],
                    "summary": "A paper-local result.",
                },
                {
                    "id": "rational_singularity",
                    "label": "Rational singularity",
                    "entity_type": "property",
                    "aliases": [],
                    "summary": "A reusable singularity property.",
                },
            ],
            "edges": [],
        },
    )

    results = search_local(root, "representation rational singularity theorem", limit=10)

    assert any(item["id"] == "rational_singularity" for item in results)
    assert all(item["id"] != "theorem_2_1_representation_growth" for item in results)
