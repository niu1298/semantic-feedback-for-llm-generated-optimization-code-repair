from __future__ import annotations

import json
import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from src.orthought_adapter import ORThoughtAdapter


def test_difficulty_score_uses_variables_plus_constraints() -> None:
    adapter = ORThoughtAdapter("logior")

    assert adapter._difficulty_score({"details": {"variables_num": 12, "constraints_num": 20}}) == 32.0


def test_difficulty_score_missing_data_sorts_last() -> None:
    adapter = ORThoughtAdapter("logior")

    assert adapter._difficulty_score({}) == float("inf")


def test_load_problems_applies_offset_after_difficulty_sort(tmp_path: Path) -> None:
    processed = tmp_path / "datasets" / "processed" / "LogiOR"
    summary_dir = tmp_path / "datasets" / "summary"
    processed.mkdir(parents=True)
    summary_dir.mkdir(parents=True)
    summary = {
        "prob_001": {"description": "hard", "details": {"variables_num": 10, "constraints_num": 10}},
        "prob_002": {"description": "easy", "details": {"variables_num": 1, "constraints_num": 2}},
        "prob_003": {"description": "middle", "details": {"variables_num": 5, "constraints_num": 5}},
        "prob_004": {"description": "next", "details": {"variables_num": 3, "constraints_num": 4}},
    }
    (summary_dir / "summary_logior.json").write_text(json.dumps(summary), encoding="utf-8")
    for problem_id in summary:
        problem_dir = processed / problem_id
        problem_dir.mkdir()
        (problem_dir / "question.txt").write_text(problem_id, encoding="utf-8")

    adapter = ORThoughtAdapter("logior", orthought_root=tmp_path)
    problems = adapter.load_problems(limit=2, offset=1)

    assert [problem["problem_id"] for problem in problems] == ["prob_004", "prob_003"]
    assert [problem["metadata"]["difficulty_rank"] for problem in problems] == [1, 2]
