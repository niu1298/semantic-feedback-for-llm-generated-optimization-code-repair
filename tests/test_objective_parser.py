from __future__ import annotations

import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from src.objective_parser import parse_objective


def test_objective_parser_parses_explicit_objective() -> None:
    assert parse_objective("hello\nOBJECTIVE=123.45\n") == 123.45


def test_objective_parser_ignores_unlabeled_numbers() -> None:
    assert parse_objective("first 1.0 second -2.5") is None


def test_objective_parser_parses_objective_30() -> None:
    assert parse_objective("OBJECTIVE=30.0\n") == 30.0


def test_objective_parser_does_not_parse_runtime_error_noise() -> None:
    text = "Academic license expires 2026-11-30\nTraceback line 42\n"

    assert parse_objective(text, returncode=1) is None


def test_objective_parser_still_allows_explicit_objective_on_nonzero_returncode() -> None:
    assert parse_objective("warning\nOBJECTIVE=30.0\n", returncode=1) == 30.0
