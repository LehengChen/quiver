"""Static GitHub Pages export."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from quiver.project import append_event, now_iso, require_project, slugify, write_json
from quiver.site_data import build_site_payloads


FALLBACK_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Quiver Concept Map</title>
  <style>
    body { margin: 0; font-family: Inter, ui-sans-serif, system-ui, sans-serif; background: #fff; color: #182230; }
    main { max-width: 920px; margin: 0 auto; padding: 32px 20px; }
    h1 { font-size: 24px; margin: 0 0 8px; }
    p { color: #475467; line-height: 1.5; }
    a { color: #175cd3; }
  </style>
</head>
<body>
  <main>
    <h1>Quiver Concept Map</h1>
    <p>The React visualization bundle was not available, but the site data was exported.</p>
    <p>Open <a href="./graph.json">graph.json</a>, <a href="./analysis.json">analysis.json</a>, or build the frontend from <code>web/</code>.</p>
  </main>
</body>
</html>
"""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _copy_dist(site_dir: Path, dist_dir: Path) -> bool:
    if not (dist_dir / "index.html").exists():
        return False
    for item in dist_dir.iterdir():
        target = site_dir / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
    return True


def _build_react_app(web_dir: Path) -> bool:
    if not (web_dir / "package.json").exists():
        return False
    try:
        subprocess.run(["npm", "run", "build"], cwd=web_dir, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return True


def _site_files(site_dir: Path) -> list[str]:
    return sorted(path.relative_to(site_dir).as_posix() for path in site_dir.rglob("*") if path.is_file())


def _copy_frontend(site_dir: Path) -> tuple[str, str]:
    repo = _repo_root()
    web_dir = repo / "web"
    dist_dir = web_dir / "dist"
    if _copy_dist(site_dir, dist_dir):
        return "react", "existing_dist"
    if _build_react_app(web_dir) and _copy_dist(site_dir, dist_dir):
        return "react", "npm_build"
    (site_dir / "index.html").write_text(FALLBACK_HTML, encoding="utf-8")
    return "fallback", "fallback_html"


def _unique_collection_id(seed: str, used: set[str]) -> str:
    base = slugify(seed, limit=56)
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}-{index}"
        index += 1
    used.add(candidate)
    return candidate


def _collection_entry(collection_id: str, manifest: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    base = f"{prefix.rstrip('/')}/" if prefix else ""
    return {
        "id": collection_id,
        "project_id": manifest.get("project_id") or collection_id,
        "title": manifest.get("title") or collection_id,
        "graph": f"{base}graph.json",
        "analysis": f"{base}analysis.json",
        "manifest": f"{base}manifest.json",
    }


def _collections_payload(title: str, entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "quiver.site_collections.v1",
        "title": title,
        "generated_at": now_iso(),
        "collections": entries,
    }


def build_site(root: Path) -> dict[str, Any]:
    root = require_project(root)
    graph, analysis, manifest = build_site_payloads(root)
    site_dir = root / "results" / "site"
    if site_dir.exists():
        shutil.rmtree(site_dir)
    site_dir.mkdir(parents=True, exist_ok=True)

    frontend, build_source = _copy_frontend(site_dir)

    write_json(site_dir / "graph.json", graph)
    write_json(site_dir / "analysis.json", analysis)
    manifest["frontend"] = frontend
    manifest["build_source"] = build_source
    collection_id = slugify(str(manifest.get("project_id") or root.name), limit=56)
    write_json(site_dir / "collections.json", _collections_payload(manifest.get("title") or collection_id, [_collection_entry(collection_id, manifest)]))
    manifest["files"] = sorted(set([*_site_files(site_dir), "manifest.json"]))
    write_json(site_dir / "manifest.json", manifest)
    files = _site_files(site_dir)
    append_event(root, "site.build", {"path": site_dir.relative_to(root).as_posix(), "frontend": frontend})
    return {"path": site_dir.relative_to(root).as_posix(), "files": files, "frontend": frontend}


def build_collections_site(output: Path, roots: list[Path]) -> dict[str, Any]:
    if not roots:
        raise ValueError("at least one project is required")
    site_dir = output.resolve()
    if site_dir.exists():
        shutil.rmtree(site_dir)
    site_dir.mkdir(parents=True, exist_ok=True)
    frontend, build_source = _copy_frontend(site_dir)

    entries: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    first_payload: tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None = None
    for project in roots:
        root = require_project(project)
        graph, analysis, manifest = build_site_payloads(root)
        if first_payload is None:
            first_payload = (graph, analysis, dict(manifest))
        collection_id = _unique_collection_id(str(manifest.get("project_id") or root.name), used_ids)
        collection_dir = site_dir / "collections" / collection_id
        collection_dir.mkdir(parents=True, exist_ok=True)
        manifest["frontend"] = frontend
        manifest["build_source"] = build_source
        manifest["files"] = ["analysis.json", "graph.json", "manifest.json"]
        write_json(collection_dir / "graph.json", graph)
        write_json(collection_dir / "analysis.json", analysis)
        write_json(collection_dir / "manifest.json", manifest)
        entries.append(_collection_entry(collection_id, manifest, prefix=f"collections/{collection_id}"))
        append_event(root, "site.collection_build", {"path": str(site_dir), "collection_id": collection_id, "frontend": frontend})

    assert first_payload is not None
    graph, analysis, first_manifest = first_payload
    write_json(site_dir / "graph.json", graph)
    write_json(site_dir / "analysis.json", analysis)
    title = "Quiver concept collections" if len(entries) > 1 else entries[0]["title"]
    root_manifest = {
        **first_manifest,
        "project_id": slugify(site_dir.name, limit=56),
        "title": title,
        "source_graph": "collections.json",
        "frontend": frontend,
        "build_source": build_source,
        "collection_count": len(entries),
    }
    write_json(site_dir / "collections.json", _collections_payload(title, entries))
    root_manifest["files"] = sorted(set([*_site_files(site_dir), "manifest.json"]))
    write_json(site_dir / "manifest.json", root_manifest)
    files = _site_files(site_dir)
    return {"path": str(site_dir), "files": files, "frontend": frontend, "collections": len(entries)}
