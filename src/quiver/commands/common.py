"""Shared CLI helpers."""

from __future__ import annotations

import json
from typing import Any

import typer


def envelope(schema: str, items: list[Any], **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"schema_version": schema, "items": items}
    payload.update(extra)
    return payload


def echo_json(obj: Any) -> None:
    typer.echo(json.dumps(obj, indent=2, ensure_ascii=False))
