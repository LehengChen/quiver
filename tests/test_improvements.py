from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_improvements_registry_validates() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "improvements" / "tools" / "qi.py"), "validate"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "ok" in completed.stdout
