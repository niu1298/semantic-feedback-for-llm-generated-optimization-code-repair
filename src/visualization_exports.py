"""Visualization-ready exports derived from saved experiment results."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .result_schema import ExperimentResult, ProblemResult, RoundResult


TREND_FIELDS = [
    "problem_id",
    "model",
    "strategy",
    "round_index",
    "valid",
    "converged_by_this_round",
    "error_type",
    "parsed_objective",
    "expected_objective",
    "objective_gap",
    "llm_calls_so_far",
    "semantic_calls_so_far",
    "solver_calls_so_far",
    "wall_time_so_far",
    "round_wall_time",
    "semantic_score",
    "static_check_passed",
    "semantic_check_passed",
    "executed",
    "execution_success",
]

PROBLEM_SUMMARY_FIELDS = [
    "problem_id",
    "model",
    "strategy",
    "final_valid",
    "rounds_to_first_valid",
    "llm_calls_to_first_valid",
    "semantic_calls_to_first_valid",
    "solver_calls_to_first_valid",
    "wall_time_to_first_valid",
    "invalid_solver_calls_before_valid",
    "best_objective_gap",
    "final_objective_gap",
]

RUN_SUMMARY_FIELDS = [
    "model",
    "strategy",
    "num_problems",
    "pass_rate",
    "solved_count",
    "avg_rounds_to_first_valid",
    "avg_llm_calls_to_first_valid",
    "avg_semantic_calls_to_first_valid",
    "avg_solver_calls_to_first_valid",
    "avg_wall_time_to_first_valid",
    "avg_invalid_solver_calls_before_valid",
    "avg_best_objective_gap",
    "avg_final_objective_gap",
]


def export_run_visualizations(result: ExperimentResult, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    trend_path = out_dir / "trend_records.csv"
    problem_path = out_dir / "problem_summary.csv"
    run_path = out_dir / "run_summary.json"

    trend_rows = build_trend_records(result)
    problem_rows = build_problem_summary_rows(result)
    run_summary = build_run_summary(result, problem_rows)

    write_csv(trend_path, TREND_FIELDS, trend_rows)
    write_csv(problem_path, PROBLEM_SUMMARY_FIELDS, problem_rows)
    run_path.write_text(json.dumps(run_summary, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "trend_records": trend_path,
        "problem_summary": problem_path,
        "run_summary": run_path,
    }


def export_merged_plot_ready(results_paths: list[str | Path], out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    results = [load_result(path) for path in results_paths]
    trend_rows = [row for result in results for row in build_trend_records(result)]
    problem_rows = [row for result in results for row in build_problem_summary_rows(result)]
    run_rows = [build_run_summary(result, build_problem_summary_rows(result)) for result in results]

    convergence_path = out_dir / "convergence_plot_ready.csv"
    accuracy_path = out_dir / "accuracy_plot_ready.csv"
    cost_quality_path = out_dir / "cost_quality_plot_ready.csv"

    write_csv(convergence_path, _convergence_plot_fields(), build_convergence_plot_rows(trend_rows))
    write_csv(accuracy_path, RUN_SUMMARY_FIELDS, run_rows)
    write_csv(cost_quality_path, _cost_quality_fields(), build_cost_quality_rows(problem_rows, trend_rows))
    return {
        "convergence_plot_ready": convergence_path,
        "accuracy_plot_ready": accuracy_path,
        "cost_quality_plot_ready": cost_quality_path,
    }


def load_result(path: str | Path) -> ExperimentResult:
    payload = json.loads(Path(path).resolve().read_text(encoding="utf-8"))
    return ExperimentResult.from_dict(payload)


def build_trend_records(result: ExperimentResult) -> list[dict[str, Any]]:
    model = model_label(result.config)
    rows: list[dict[str, Any]] = []
    for problem in result.problems:
        llm_calls = 0
        semantic_calls = 0
        solver_calls = 0
        wall_time = 0.0
        converged = False
        for round_result in problem.rounds:
            llm_calls += round_result.llm_calls
            semantic_calls += round_result.semantic_calls
            solver_calls += round_result.solver_calls
            wall_time += round_result.wall_time_seconds
            if round_result.valid is True:
                converged = True
            rows.append(
                {
                    "problem_id": problem.problem_id,
                    "model": model,
                    "strategy": problem.strategy,
                    "round_index": round_result.round_index,
                    "valid": round_result.valid,
                    "converged_by_this_round": converged,
                    "error_type": round_result.error_type,
                    "parsed_objective": round_result.parsed_objective,
                    "expected_objective": round_result.expected_objective,
                    "objective_gap": round_result.objective_gap,
                    "llm_calls_so_far": llm_calls,
                    "semantic_calls_so_far": semantic_calls,
                    "solver_calls_so_far": solver_calls,
                    "wall_time_so_far": wall_time,
                    "round_wall_time": round_result.wall_time_seconds,
                    "semantic_score": round_result.semantic_score,
                    "static_check_passed": round_result.static_check_passed,
                    "semantic_check_passed": round_result.semantic_check_passed,
                    "executed": round_result.executed,
                    "execution_success": round_result.execution_success,
                }
            )
    return rows


def build_problem_summary_rows(result: ExperimentResult) -> list[dict[str, Any]]:
    model = model_label(result.config)
    return [_problem_summary_row(problem, model) for problem in result.problems]


def build_run_summary(result: ExperimentResult, problem_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = problem_rows or build_problem_summary_rows(result)
    known = [row["final_valid"] for row in rows if row["final_valid"] is not None]
    solved = [row for row in rows if row["final_valid"] is True]
    strategy = rows[0]["strategy"] if rows else str(result.config.get("strategy") or "")
    return {
        "model": model_label(result.config),
        "strategy": strategy,
        "num_problems": len(rows),
        "pass_rate": _pass_rate(known),
        "solved_count": len(solved),
        "avg_rounds_to_first_valid": _mean([row["rounds_to_first_valid"] for row in solved]),
        "avg_llm_calls_to_first_valid": _mean([row["llm_calls_to_first_valid"] for row in solved]),
        "avg_semantic_calls_to_first_valid": _mean([row["semantic_calls_to_first_valid"] for row in solved]),
        "avg_solver_calls_to_first_valid": _mean([row["solver_calls_to_first_valid"] for row in solved]),
        "avg_wall_time_to_first_valid": _mean([row["wall_time_to_first_valid"] for row in solved]),
        "avg_invalid_solver_calls_before_valid": _mean(
            [row["invalid_solver_calls_before_valid"] for row in solved]
        ),
        "avg_best_objective_gap": _mean([row["best_objective_gap"] for row in rows]),
        "avg_final_objective_gap": _mean([row["final_objective_gap"] for row in rows]),
    }


def build_convergence_plot_rows(trend_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    for row in trend_rows:
        key = (str(row["model"]), str(row["strategy"]), int(row["round_index"]))
        groups.setdefault(key, []).append(row)

    output: list[dict[str, Any]] = []
    for (model, strategy, round_index), rows in sorted(groups.items()):
        output.append(
            {
                "model": model,
                "strategy": strategy,
                "round_index": round_index,
                "num_records": len(rows),
                "converged_count": sum(1 for row in rows if row["converged_by_this_round"] is True),
                "pass_rate_by_round": _pass_rate(
                    [bool(row["converged_by_this_round"]) for row in rows]
                ),
                "avg_objective_gap": _mean([row["objective_gap"] for row in rows]),
                "avg_solver_calls_so_far": _mean([row["solver_calls_so_far"] for row in rows]),
                "avg_wall_time_so_far": _mean([row["wall_time_so_far"] for row in rows]),
            }
        )
    return output


def build_cost_quality_rows(
    problem_rows: list[dict[str, Any]],
    trend_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    totals: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in trend_rows:
        key = (str(row["model"]), str(row["strategy"]), str(row["problem_id"]))
        current = totals.setdefault(
            key,
            {
                "total_llm_calls": 0,
                "total_semantic_calls": 0,
                "total_solver_calls": 0,
                "total_wall_time": 0.0,
            },
        )
        current["total_llm_calls"] = row["llm_calls_so_far"]
        current["total_semantic_calls"] = row["semantic_calls_so_far"]
        current["total_solver_calls"] = row["solver_calls_so_far"]
        current["total_wall_time"] = row["wall_time_so_far"]

    rows: list[dict[str, Any]] = []
    for problem in problem_rows:
        key = (str(problem["model"]), str(problem["strategy"]), str(problem["problem_id"]))
        total = totals.get(key, {})
        rows.append(
            {
                "model": problem["model"],
                "strategy": problem["strategy"],
                "problem_id": problem["problem_id"],
                "final_valid": problem["final_valid"],
                "rounds_to_first_valid": problem["rounds_to_first_valid"],
                "best_objective_gap": problem["best_objective_gap"],
                "final_objective_gap": problem["final_objective_gap"],
                "total_llm_calls": total.get("total_llm_calls", 0),
                "total_semantic_calls": total.get("total_semantic_calls", 0),
                "total_solver_calls": total.get("total_solver_calls", 0),
                "total_wall_time": total.get("total_wall_time", 0.0),
            }
        )
    return rows


def model_label(config: dict[str, Any]) -> str:
    return str(config.get("llm_model") or config.get("model") or "unknown")


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def _problem_summary_row(problem: ProblemResult, model: str) -> dict[str, Any]:
    first_valid = _first_valid_index(problem.rounds)
    prefix = problem.rounds if first_valid is None else problem.rounds[: first_valid + 1]
    gaps = [round.objective_gap for round in problem.rounds if round.objective_gap is not None]
    return {
        "problem_id": problem.problem_id,
        "model": model,
        "strategy": problem.strategy,
        "final_valid": problem.final_valid,
        "rounds_to_first_valid": None if first_valid is None else first_valid + 1,
        "llm_calls_to_first_valid": None if first_valid is None else sum(round.llm_calls for round in prefix),
        "semantic_calls_to_first_valid": None
        if first_valid is None
        else sum(round.semantic_calls for round in prefix),
        "solver_calls_to_first_valid": None
        if first_valid is None
        else sum(round.solver_calls for round in prefix),
        "wall_time_to_first_valid": None
        if first_valid is None
        else sum(round.wall_time_seconds for round in prefix),
        "invalid_solver_calls_before_valid": None
        if first_valid is None
        else sum(round.solver_calls for round in prefix[:-1] if round.valid is not True),
        "best_objective_gap": None if not gaps else min(float(gap) for gap in gaps),
        "final_objective_gap": problem.objective_gap,
    }


def _first_valid_index(rounds: list[RoundResult]) -> int | None:
    for index, round_result in enumerate(rounds):
        if round_result.valid is True:
            return index
    return None


def _convergence_plot_fields() -> list[str]:
    return [
        "model",
        "strategy",
        "round_index",
        "num_records",
        "converged_count",
        "pass_rate_by_round",
        "avg_objective_gap",
        "avg_solver_calls_so_far",
        "avg_wall_time_so_far",
    ]


def _cost_quality_fields() -> list[str]:
    return [
        "model",
        "strategy",
        "problem_id",
        "final_valid",
        "rounds_to_first_valid",
        "best_objective_gap",
        "final_objective_gap",
        "total_llm_calls",
        "total_semantic_calls",
        "total_solver_calls",
        "total_wall_time",
    ]


def _pass_rate(values: list[bool]) -> float | None:
    if not values:
        return None
    return sum(1 for value in values if value) / len(values)


def _mean(values: list[float | int | None]) -> float | None:
    concrete = [float(value) for value in values if value is not None]
    if not concrete:
        return None
    return sum(concrete) / len(concrete)


def _csv_value(value: object) -> object:
    return "" if value is None else value
