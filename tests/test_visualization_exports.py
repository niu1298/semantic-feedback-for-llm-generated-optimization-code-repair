from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from src.result_schema import ExperimentResult, ProblemResult, RoundResult
from src.visualization_exports import (
    PROBLEM_SUMMARY_FIELDS,
    RUN_SUMMARY_FIELDS,
    TREND_FIELDS,
    build_problem_summary_rows,
    build_run_summary,
    build_trend_records,
    export_merged_plot_ready,
    export_run_visualizations,
)


def sample_result() -> ExperimentResult:
    return ExperimentResult(
        created_at="2026-05-06T00:00:00+00:00",
        config={"llm_model": "gpt-test", "strategy": "execution_only"},
        problems=[
            ProblemResult(
                strategy="execution_only",
                problem_id="p1",
                final_valid=True,
                objective_gap=0.0,
                rounds=[
                    RoundResult(
                        strategy="execution_only",
                        problem_id="p1",
                        round_index=0,
                        valid=False,
                        error_type="objective_mismatch",
                        llm_calls=1,
                        solver_calls=1,
                        wall_time_seconds=2.0,
                        parsed_objective=1.0,
                        expected_objective=7.0,
                        objective_gap=6.0,
                        static_check_passed=True,
                        executed=True,
                        execution_success=True,
                    ),
                    RoundResult(
                        strategy="execution_only",
                        problem_id="p1",
                        round_index=1,
                        valid=True,
                        llm_calls=1,
                        solver_calls=1,
                        wall_time_seconds=3.0,
                        parsed_objective=7.0,
                        expected_objective=7.0,
                        objective_gap=0.0,
                        static_check_passed=True,
                        executed=True,
                        execution_success=True,
                    ),
                ],
            )
        ],
    )


def test_trend_records_schema() -> None:
    rows = build_trend_records(sample_result())

    assert list(rows[0]) == TREND_FIELDS
    assert rows[0]["converged_by_this_round"] is False
    assert rows[1]["converged_by_this_round"] is True
    assert rows[1]["llm_calls_so_far"] == 2
    assert rows[1]["solver_calls_so_far"] == 2


def test_problem_summary_first_valid_fields() -> None:
    rows = build_problem_summary_rows(sample_result())

    assert list(rows[0]) == PROBLEM_SUMMARY_FIELDS
    assert rows[0]["rounds_to_first_valid"] == 2
    assert rows[0]["llm_calls_to_first_valid"] == 2
    assert rows[0]["solver_calls_to_first_valid"] == 2
    assert rows[0]["invalid_solver_calls_before_valid"] == 1
    assert rows[0]["best_objective_gap"] == 0.0


def test_run_summary_fields() -> None:
    summary = build_run_summary(sample_result())

    assert list(summary) == RUN_SUMMARY_FIELDS
    assert summary["model"] == "gpt-test"
    assert summary["pass_rate"] == 1.0
    assert summary["solved_count"] == 1
    assert summary["avg_rounds_to_first_valid"] == 2.0


def test_export_run_visualizations_writes_files(tmp_path: Path) -> None:
    paths = export_run_visualizations(sample_result(), tmp_path)

    assert paths["trend_records"].is_file()
    assert paths["problem_summary"].is_file()
    assert paths["run_summary"].is_file()
    with paths["run_summary"].open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload["model"] == "gpt-test"


def test_merged_plot_ready_csv_export(tmp_path: Path) -> None:
    result_path = tmp_path / "results.json"
    result_path.write_text(sample_result().to_json(), encoding="utf-8")

    paths = export_merged_plot_ready([result_path], tmp_path / "merged")

    assert paths["convergence_plot_ready"].is_file()
    assert paths["accuracy_plot_ready"].is_file()
    assert paths["cost_quality_plot_ready"].is_file()
    with paths["accuracy_plot_ready"].open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["model"] == "gpt-test"
    assert rows[0]["pass_rate"] == "1.0"
