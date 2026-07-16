"""Subprocess executor for static-passing generated code."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .objective_parser import parse_objective


RUNNER_SOURCE = '''"""Import and run generated optimization code."""

from __future__ import annotations

import importlib
import sys
import traceback


def main() -> int:
    try:
        module = importlib.import_module("generated_code")
        target = None
        for name in ("solve_model", "solve"):
            candidate = getattr(module, name, None)
            if callable(candidate):
                target = candidate
                break
        if target is None:
            print("No solve_model() or solve() function found.", file=sys.stderr)
            return 2
        result = target()
        if result is not None:
            print(f"OBJECTIVE={result}")
        return 0
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def execute_generated_code(
    code: str,
    run_dir: str | Path,
    timeout_seconds: int,
    expected_answer_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del expected_answer_metadata
    run_path = Path(run_dir)
    run_path.mkdir(parents=True, exist_ok=True)

    generated_path = run_path / "generated_code.py"
    runner_path = run_path / "runner.py"
    stdout_path = run_path / "stdout.txt"
    stderr_path = run_path / "stderr.txt"

    generated_path.write_text(code, encoding="utf-8")
    runner_path.write_text(RUNNER_SOURCE, encoding="utf-8")

    timeout = False
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [sys.executable, str(runner_path.name)],
            cwd=run_path,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        timeout = True
        returncode = -1
        stdout = _decode_timeout_output(exc.stdout)
        stderr = _decode_timeout_output(exc.stderr)
    elapsed_seconds = time.monotonic() - started

    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")

    objective = parse_objective(stdout, returncode=returncode)
    error_type: str | None = None
    if timeout:
        error_type = "timeout"
    elif returncode != 0:
        error_type = "runtime_error"
    elif objective is None:
        error_type = "no_objective"

    return {
        "executed": True,
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "timeout": timeout,
        "objective": objective,
        "error_type": error_type,
        "run_dir": str(run_path),
        "elapsed_seconds": elapsed_seconds,
        "generated_code_path": str(generated_path),
        "runner_path": str(runner_path),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }


def _decode_timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
