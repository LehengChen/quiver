from __future__ import annotations

from pathlib import Path

from quiver.project import find_project_root, init_project, read_json, read_jsonl, write_json, write_jsonl


def test_init_project_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    init_project(root)
    init_project(root)
    assert (root / "quiver.toml").exists()
    assert (root / ".quiver" / "config.json").exists()
    assert (root / "sources" / "papers").is_dir()
    assert read_json(root / "results" / "normalized" / "concept_graph.json")["schema_version"] == "quiver.graph.v1"


def test_find_project_root_from_child(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    child = root / "sources" / "papers"
    init_project(root)
    assert find_project_root(child) == root.resolve()


def test_atomic_json_helpers(tmp_path: Path) -> None:
    path = tmp_path / "state" / "item.json"
    write_json(path, {"a": 1})
    assert read_json(path) == {"a": 1}
    jsonl = tmp_path / "state" / "items.jsonl"
    write_jsonl(jsonl, [{"a": 1}, {"a": 2}])
    assert read_jsonl(jsonl) == [{"a": 1}, {"a": 2}]
