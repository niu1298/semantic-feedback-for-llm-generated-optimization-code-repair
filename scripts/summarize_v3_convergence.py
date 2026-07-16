#!/usr/bin/env python3
"""Build CSV summaries from V3 convergence JSONL logs."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run_dir", required=True, help="Run directory containing convergence JSONL logs.")
    parser.add_argument(
        "--output_dir",
        default=None,
        help="Directory for CSV outputs. Defaults to --run_dir.",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    output_dir = Path(args.output_dir) if args.output_dir else run_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    round_records = _read_jsonl(run_dir / "convergence_rounds.jsonl")
    problem_records = _read_jsonl(run_dir / "convergence_problem_summary.jsonl")
    feedback_records = _read_feedback_uptake(run_dir)

    config_summary = _per_config_summary(problem_records, round_records)
    _warn_low_parse_success(config_summary)
    _write_csv(output_dir / "per_round_metrics.csv", round_records)
    _write_csv(output_dir / "per_problem_summary.csv", problem_records)
    _write_csv(output_dir / "per_config_summary.csv", config_summary)
    _write_csv(output_dir / "retrospective_gate_summary.csv", _retrospective_summary(round_records))
    _write_csv(output_dir / "spec_pipeline_summary.csv", _spec_pipeline_summary(round_records))
    _write_csv(output_dir / "feedback_uptake_summary.csv", _feedback_uptake_summary(feedback_records))
    _write_csv(output_dir / "multi_advisor_summary.csv", _multi_advisor_summary(round_records))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _read_feedback_uptake(run_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in run_dir.rglob("feedback_uptake.jsonl"):
        records.extend(_read_jsonl(path))
    return records


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})


def _per_config_summary(
    problem_records: list[dict[str, Any]],
    round_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    problems_by_config: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    rounds_by_config: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in problem_records:
        problems_by_config[_summary_key(row)].append(row)
    for row in round_records:
        rounds_by_config[_summary_key(row)].append(row)

    summaries: list[dict[str, Any]] = []
    for key, problems in sorted(problems_by_config.items()):
        config_name, strategy_name, advisory_mode = key
        rounds = rounds_by_config.get(key, [])
        solved = [row for row in problems if row.get("solved") is True]
        first_valid_rounds = [
            int(row["first_valid_round"])
            for row in solved
            if row.get("first_valid_round") is not None
        ]
        total_solver_calls = sum(int(row.get("total_solver_calls") or 0) for row in problems)
        total_semantic_calls = sum(int(row.get("total_semantic_calls") or 0) for row in problems)
        semantic_check_rows = [row for row in rounds if _has_semantic_parse_field(row)]
        parse_success_count = sum(1 for row in semantic_check_rows if _is_true(row.get("semantic_parse_success")))
        empty_response_count = sum(1 for row in semantic_check_rows if _is_true(row.get("semantic_empty_response")))
        parse_failed_count = len(semantic_check_rows) - parse_success_count
        intended_rows = [row for row in rounds if row.get("intended_spec_parse_success") is not None]
        extracted_rows = [row for row in rounds if row.get("extracted_spec_parse_success") is not None]
        comparison_rows = [row for row in rounds if row.get("spec_comparison_parse_success") is not None]
        disagreement_rows = [row for row in rounds if row.get("should_execute_disagreement") is not None]
        merged_types = Counter()
        for row in rounds:
            for error_type in row.get("merged_diagnosed_error_types") or []:
                merged_types[str(error_type)] += 1
        final_errors = Counter(str(row.get("final_error_type") or "unknown") for row in problems)
        objective_gap_by_round: dict[str, list[float]] = defaultdict(list)
        for row in rounds:
            gap = row.get("objective_gap")
            if gap is None:
                continue
            try:
                objective_gap_by_round[str(row.get("round"))].append(float(gap))
            except (TypeError, ValueError):
                continue
        avg_gap_by_round = {
            key: sum(values) / len(values)
            for key, values in sorted(objective_gap_by_round.items())
            if values
        }
        summaries.append(
            {
                "config_name": config_name,
                "strategy_name": strategy_name,
                "advisory_mode": advisory_mode,
                "total_problems": len(problems),
                "solved_count": len(solved),
                "pass_rate": len(solved) / len(problems) if problems else 0.0,
                "average_first_valid_round_among_solved": (
                    sum(first_valid_rounds) / len(first_valid_rounds) if first_valid_rounds else None
                ),
                "median_first_valid_round_among_solved": (
                    statistics.median(first_valid_rounds) if first_valid_rounds else None
                ),
                "total_llm_generation_calls": sum(
                    int(row.get("total_llm_generation_calls") or 0) for row in problems
                ),
                "total_semantic_calls": total_semantic_calls,
                "total_solver_calls": total_solver_calls,
                "semantic_checks_total": len(semantic_check_rows),
                "semantic_parse_success_count": parse_success_count,
                "semantic_parse_failed_count": parse_failed_count,
                "semantic_empty_response_count": empty_response_count,
                "semantic_parse_success_rate": (
                    parse_success_count / len(semantic_check_rows) if semantic_check_rows else None
                ),
                "intended_spec_parse_success_rate": _success_rate(
                    intended_rows, "intended_spec_parse_success"
                ),
                "extracted_spec_parse_success_rate": _success_rate(
                    extracted_rows, "extracted_spec_parse_success"
                ),
                "spec_comparison_parse_success_rate": _success_rate(
                    comparison_rows, "spec_comparison_parse_success"
                ),
                "advisor_count": _max_numeric(rounds, "advisor_count"),
                "should_execute_disagreement_rate": (
                    sum(1 for row in disagreement_rows if _is_true(row.get("should_execute_disagreement")))
                    / len(disagreement_rows)
                    if disagreement_rows
                    else None
                ),
                "merged_diagnosed_error_type_distribution": dict(merged_types),
                "solver_calls_per_solved_problem": (
                    total_solver_calls / len(solved) if solved else None
                ),
                "semantic_calls_per_solved_problem": (
                    total_semantic_calls / len(solved) if solved else None
                ),
                "final_error_type_distribution": dict(final_errors),
                "average_objective_gap_by_round": avg_gap_by_round,
            }
        )
    return summaries


def _spec_pipeline_summary(round_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_config: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in round_records:
        by_config[_summary_key(row)].append(row)
    for key, records in sorted(by_config.items()):
        config_name, strategy_name, advisory_mode = key
        intended_rows = [row for row in records if row.get("intended_spec_parse_success") is not None]
        extracted_rows = [row for row in records if row.get("extracted_spec_parse_success") is not None]
        comparison_rows = [row for row in records if row.get("spec_comparison_parse_success") is not None]
        rows.append(
            {
                "config_name": config_name,
                "strategy_name": strategy_name,
                "advisory_mode": advisory_mode,
                "round_count": len(records),
                "intended_spec_checks": len(intended_rows),
                "intended_spec_parse_success_rate": _success_rate(
                    intended_rows, "intended_spec_parse_success"
                ),
                "extracted_spec_checks": len(extracted_rows),
                "extracted_spec_parse_success_rate": _success_rate(
                    extracted_rows, "extracted_spec_parse_success"
                ),
                "spec_comparison_checks": len(comparison_rows),
                "spec_comparison_parse_success_rate": _success_rate(
                    comparison_rows, "spec_comparison_parse_success"
                ),
                "avg_intended_variable_count": _avg_numeric(intended_rows, "intended_spec_variable_count"),
                "avg_intended_constraint_count": _avg_numeric(intended_rows, "intended_spec_constraint_count"),
                "avg_extracted_variable_count": _avg_numeric(extracted_rows, "extracted_spec_variable_count"),
                "avg_extracted_constraint_count": _avg_numeric(extracted_rows, "extracted_spec_constraint_count"),
            }
        )
    return rows


def _feedback_uptake_summary(feedback_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_config: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in feedback_records:
        by_config[_summary_key(row)].append(row)
    for key, records in sorted(by_config.items()):
        config_name, strategy_name, advisory_mode = key
        total = len(records)
        implemented = sum(1 for row in records if _is_true(row.get("implemented_next_round")))
        resolved = sum(1 for row in records if _is_true(row.get("error_resolved")))
        new_error = sum(1 for row in records if _is_true(row.get("new_error_introduced")))
        gap_improved = sum(1 for row in records if _is_true(row.get("objective_gap_improved")))
        implemented_and_solved = sum(
            1
            for row in records
            if _is_true(row.get("implemented_next_round")) and _is_true(row.get("eventual_solved"))
        )
        rows.append(
            {
                "config_name": config_name,
                "strategy_name": strategy_name,
                "advisory_mode": advisory_mode,
                "feedback_items_total": total,
                "feedback_items_implemented": implemented,
                "feedback_items_resolved": resolved,
                "feedback_new_error_count": new_error,
                "feedback_objective_gap_improved_count": gap_improved,
                "implementation_rate": implemented / total if total else None,
                "resolution_rate": resolved / total if total else None,
                "new_error_rate": new_error / total if total else None,
                "objective_gap_improvement_rate": gap_improved / total if total else None,
                "implemented_and_solved_count": implemented_and_solved,
            }
        )
    return rows


def _multi_advisor_summary(round_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_config: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in round_records:
        if row.get("advisor_count") is not None:
            by_config[_summary_key(row)].append(row)
    for key, records in sorted(by_config.items()):
        config_name, strategy_name, advisory_mode = key
        disagreement = [row for row in records if row.get("should_execute_disagreement") is not None]
        merged = Counter()
        for row in records:
            for error_type in row.get("merged_diagnosed_error_types") or []:
                merged[str(error_type)] += 1
        rows.append(
            {
                "config_name": config_name,
                "strategy_name": strategy_name,
                "advisory_mode": advisory_mode,
                "round_count": len(records),
                "advisor_count_max": _max_numeric(records, "advisor_count"),
                "should_execute_disagreement_rate": (
                    sum(1 for row in disagreement if _is_true(row.get("should_execute_disagreement")))
                    / len(disagreement)
                    if disagreement
                    else None
                ),
                "merged_diagnosed_error_type_distribution": dict(merged),
            }
        )
    return rows


def _retrospective_summary(round_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_config: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in round_records:
        if row.get("retrospective_gate_would_skip") is not None:
            by_config[_summary_key(row)].append(row)
    for key, records in sorted(by_config.items()):
        config_name, strategy_name, advisory_mode = key
        would_skip = [row for row in records if row.get("retrospective_gate_would_skip") is True]
        true_rejections = [row for row in records if row.get("retrospective_true_rejection") is True]
        false_rejections = [row for row in records if row.get("retrospective_false_rejection") is True]
        good_code = [row for row in records if row.get("valid_solution") is True]
        total = len(records)
        rows.append(
            {
                "config_name": config_name,
                "strategy_name": strategy_name,
                "advisory_mode": advisory_mode,
                "total_advisory_checks": total,
                "would_skip_count": len(would_skip),
                "would_skip_rate": len(would_skip) / total if total else 0.0,
                "true_rejection_count": len(true_rejections),
                "false_rejection_count": len(false_rejections),
                "rejection_accuracy": len(true_rejections) / len(would_skip) if would_skip else None,
                "false_rejection_rate": len(false_rejections) / len(good_code) if good_code else None,
                "false_rejection_rate_among_skipped": (
                    len(false_rejections) / len(would_skip) if would_skip else None
                ),
                "estimated_solver_calls_saved": len(would_skip),
                "estimated_solver_call_saving_rate": len(would_skip) / total if total else 0.0,
            }
        )
    return rows


def _warn_low_parse_success(rows: list[dict[str, Any]], threshold: float = 0.8) -> None:
    for row in rows:
        total = int(row.get("semantic_checks_total") or 0)
        if total <= 0:
            continue
        rate = row.get("semantic_parse_success_rate")
        try:
            numeric_rate = float(rate)
        except (TypeError, ValueError):
            continue
        if numeric_rate < threshold:
            print(
                "WARNING: Semantic judge parse success rate is low; advisory results are not reliable. "
                f"config_name={row.get('config_name')} advisory_mode={row.get('advisory_mode')} "
                f"rate={numeric_rate:.3f} threshold={threshold:.3f}"
            )


def _success_rate(rows: list[dict[str, Any]], field_name: str) -> float | None:
    if not rows:
        return None
    return sum(1 for row in rows if _is_true(row.get(field_name))) / len(rows)


def _avg_numeric(rows: list[dict[str, Any]], field_name: str) -> float | None:
    values: list[float] = []
    for row in rows:
        try:
            values.append(float(row[field_name]))
        except (KeyError, TypeError, ValueError):
            continue
    return sum(values) / len(values) if values else None


def _max_numeric(rows: list[dict[str, Any]], field_name: str) -> float | None:
    values: list[float] = []
    for row in rows:
        try:
            values.append(float(row[field_name]))
        except (KeyError, TypeError, ValueError):
            continue
    return max(values) if values else None


def _summary_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("config_name") or "unknown"),
        str(row.get("strategy_name") or row.get("strategy") or "unknown"),
        str(row.get("advisory_mode") or "unknown"),
    )


def _has_semantic_parse_field(row: dict[str, Any]) -> bool:
    return row.get("semantic_parse_success") is not None


def _is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return value


if __name__ == "__main__":
    main()
