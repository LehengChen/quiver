#!/usr/bin/env python3
"""Tiny improvement registry CLI for Quiver."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ROOT / "items"
INDEX = ROOT / "INDEX.json"

REQUIRED = {
    "schema_version",
    "id",
    "title",
    "category",
    "status",
    "severity",
    "confidence",
    "problem",
    "proposed_change",
    "acceptance_criteria",
    "observations",
    "created_at",
    "updated_at",
    "history",
}

STATUSES = {"proposed", "accepted", "implemented", "verified", "rejected"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def item_path(item_id: str) -> Path:
    return ITEMS / f"{item_id}.json"


def load_items() -> list[dict[str, Any]]:
    return [read_json(path) for path in sorted(ITEMS.glob("QI-*.json"))]


def validate_item(item: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    missing = sorted(REQUIRED - set(item))
    if missing:
        issues.append(f"{item.get('id', '<unknown>')}: missing {', '.join(missing)}")
    if item.get("schema_version") != "quiver.improvement.v1":
        issues.append(f"{item.get('id', '<unknown>')}: bad schema_version")
    if item.get("status") not in STATUSES:
        issues.append(f"{item.get('id', '<unknown>')}: bad status")
    return issues


def cmd_validate(_: argparse.Namespace) -> int:
    issues: list[str] = []
    for item in load_items():
        issues.extend(validate_item(item))
    if issues:
        for issue in issues:
            print(issue)
        return 1
    print("ok")
    return 0


def cmd_reindex(_: argparse.Namespace) -> int:
    entries = []
    for item in load_items():
        entries.append(
            {
                "id": item["id"],
                "title": item["title"],
                "status": item["status"],
                "severity": item["severity"],
                "category": item["category"],
                "path": f"items/{item['id']}.json",
            }
        )
    write_json(INDEX, {"schema_version": "quiver.improvement_index.v1", "items": entries})
    print(f"indexed {len(entries)} items")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    items = load_items()
    if args.status:
        items = [item for item in items if item["status"] == args.status]
    if args.json:
        print(json.dumps({"schema_version": "quiver.improvement_list.v1", "items": items}, indent=2, ensure_ascii=False))
    else:
        for item in items:
            print(f"{item['id']} {item['status']} {item['severity']} {item['title']}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    needle = args.text.lower()
    items = [
        item
        for item in load_items()
        if needle in " ".join(str(item.get(key, "")) for key in ["id", "title", "problem", "proposed_change"]).lower()
    ]
    for item in items:
        print(f"{item['id']} {item['status']} {item['title']}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    print(json.dumps(read_json(item_path(args.id)), indent=2, ensure_ascii=False))
    return 0


def next_id() -> str:
    ids = [int(path.stem.split("-")[1]) for path in ITEMS.glob("QI-*.json")]
    return f"QI-{(max(ids) + 1 if ids else 1):04d}"


def cmd_add(args: argparse.Namespace) -> int:
    item_id = next_id()
    ts = now_iso()
    item = {
        "schema_version": "quiver.improvement.v1",
        "id": item_id,
        "title": args.title,
        "category": args.category,
        "status": "proposed",
        "severity": args.severity,
        "confidence": args.confidence,
        "problem": args.problem,
        "proposed_change": args.proposed_change,
        "acceptance_criteria": args.acceptance_criteria,
        "observations": [],
        "created_at": ts,
        "updated_at": ts,
        "history": [],
    }
    write_json(item_path(item_id), item)
    cmd_reindex(args)
    print(item_id)
    return 0


def cmd_observe(args: argparse.Namespace) -> int:
    path = item_path(args.id)
    item = read_json(path)
    item["observations"].append({"project": args.project, "context": args.context, "created_at": now_iso(), "observed_by": args.by})
    item["updated_at"] = now_iso()
    write_json(path, item)
    cmd_reindex(args)
    return 0


def cmd_set_status(args: argparse.Namespace) -> int:
    if args.status not in STATUSES:
        raise SystemExit(f"bad status: {args.status}")
    path = item_path(args.id)
    item = read_json(path)
    old = item["status"]
    item["status"] = args.status
    item["updated_at"] = now_iso()
    item["history"].append({"at": now_iso(), "from": old, "to": args.status, "note": args.note or ""})
    write_json(path, item)
    cmd_reindex(args)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("validate")
    p.set_defaults(func=cmd_validate)
    p = sub.add_parser("reindex")
    p.set_defaults(func=cmd_reindex)
    p = sub.add_parser("list")
    p.add_argument("--status")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)
    p = sub.add_parser("search")
    p.add_argument("text")
    p.set_defaults(func=cmd_search)
    p = sub.add_parser("show")
    p.add_argument("id")
    p.set_defaults(func=cmd_show)
    p = sub.add_parser("add")
    p.add_argument("--title", required=True)
    p.add_argument("--problem", required=True)
    p.add_argument("--proposed-change", required=True)
    p.add_argument("--acceptance-criteria", required=True)
    p.add_argument("--category", default="tooling")
    p.add_argument("--severity", default="medium")
    p.add_argument("--confidence", default="medium")
    p.set_defaults(func=cmd_add)
    p = sub.add_parser("observe")
    p.add_argument("id")
    p.add_argument("--project", required=True)
    p.add_argument("--context", required=True)
    p.add_argument("--by", default="codex")
    p.set_defaults(func=cmd_observe)
    p = sub.add_parser("set-status")
    p.add_argument("id")
    p.add_argument("status")
    p.add_argument("--note")
    p.set_defaults(func=cmd_set_status)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
