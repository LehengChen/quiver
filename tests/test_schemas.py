from __future__ import annotations

import json
from pathlib import Path

from quiver.schema_defs import GRAPH_DELTA_SCHEMA


def test_checked_in_graph_delta_schema_matches_runtime_schema() -> None:
    root = Path(__file__).resolve().parents[1]
    checked_in = json.loads((root / "schemas" / "graph-delta.schema.json").read_text(encoding="utf-8"))
    assert checked_in == GRAPH_DELTA_SCHEMA
