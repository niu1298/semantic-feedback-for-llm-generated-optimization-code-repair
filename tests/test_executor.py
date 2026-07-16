from __future__ import annotations

import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from src.executor import execute_generated_code


def test_executor_runs_solve_model(tmp_path: Path) -> None:
    result = execute_generated_code(
        "def solve_model():\n    return 7.0\n",
        tmp_path,
        timeout_seconds=5,
    )

    assert result["executed"]
    assert result["returncode"] == 0
    assert result["objective"] == 7.0
    assert result["error_type"] is None
    assert (tmp_path / "stdout.txt").read_text(encoding="utf-8").strip() == "OBJECTIVE=7.0"


def test_executor_captures_runtime_error(tmp_path: Path) -> None:
    result = execute_generated_code(
        "def solve_model():\n    raise RuntimeError('boom')\n",
        tmp_path,
        timeout_seconds=5,
    )

    assert result["executed"]
    assert result["returncode"] == 1
    assert result["objective"] is None
    assert result["error_type"] == "runtime_error"
    assert "RuntimeError: boom" in result["stderr"]
