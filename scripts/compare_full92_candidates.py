#!/usr/bin/env python3
"""Compare the frozen V3 full92 candidate runs."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = Path("outputs/v3_full92_candidates/analysis")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run_dirs", nargs="+", required=True, help="method=run_dir pairs.")
    parser.add_argument("--output_dir", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    runs = {method: load_run(method, path) for method, path in parse_pairs(args.run_dirs).items()}

    comparison = build_comparison(runs)
    band_rows = build_band_breakdown(runs)
    overlap_rows = build_solve_overlap(runs)
    transition_rows = build_error_transitions(runs)
    cost_rows = build_cost_tradeoff(comparison)

    write_csv(output_dir / "full92_candidate_comparison.csv", comparison)
    write_csv(output_dir / "full92_candidate_band_breakdown.csv", band_rows)
    write_csv(output_dir / "full92_candidate_solve_overlap.csv", overlap_rows)
    write_csv(output_dir / "full92_candidate_error_transitions.csv", transition_rows)
    write_csv(output_dir / "full92_candidate_cost_tradeoff.csv", cost_rows)

    (output_dir / "full92_candidate_comparison.md").write_text(render_comparison_md(comparison), encoding="utf-8")
    (output_dir / "full92_candidate_band_breakdown.md").write_text(render_band_md(band_rows), encoding="utf-8")
    (output_dir / "full92_candidate_solve_overlap.md").write_text(render_overlap_md(overlap_rows), encoding="utf-8")
    (output_dir / "full92_candidate_error_transitions.md").write_text(render_transition_md(transition_rows), encoding="utf-8")
    (output_dir / "full92_candidate_cost_tradeoff.md").write_text(render_cost_md(cost_rows), encoding="utf-8")
    print(f"Wrote full92 comparison to {output_dir}")


def parse_pairs(items: list[str]) -> dict[str, Path]:
    pairs: dict[str, Path] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Expected method=run_dir pair, got {item}")
        method, path = item.split("=", 1)
        pairs[method] = Path(path)
    return pairs


def load_run(method: str, path: Path) -> dict[str, Any]:
    return {
        "method": method,
        "run_dir": str(path),
        "config": first(read_csv(path / "per_config_summary.csv")),
        "problems": read_csv(path / "per_problem_summary.csv"),
        "rounds": read_csv(path / "per_round_metrics.csv"),
        "audit": read_csv(path / "expanded_artifact_audit.csv"),
    }


def build_comparison(runs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for method, run in runs.items():
        config = run["config"]
        audit = run["audit"]
        problems = run["problems"]
        prompt = numbers(audit, "repair_prompt_char_count")
        feedback = numbers(audit, "feedback_char_count")
        semantic_calls = to_int(config.get("total_semantic_calls")) or 0
        spec_calls = count_spec_calls(run["rounds"])
        generation_calls = to_int(config.get("total_llm_generation_calls")) or 0
        solved = to_int(config.get("solved_count")) or 0
        rows.append(
            {
                "method": method,
                "run_dir": run["run_dir"],
                "selected_problem_count": to_int(config.get("total_problems")) or len(problems),
                "solved_count": solved,
                "pass_rate": to_float(config.get("pass_rate")),
                "solved_problem_ids": [row["problem_id"] for row in problems if is_true(row.get("solved"))],
                "avg_first_valid_round": to_float(config.get("average_first_valid_round_among_solved")),
                "median_first_valid_round": to_float(config.get("median_first_valid_round_among_solved")),
                "solver_calls": to_int(config.get("total_solver_calls")),
                "generation_calls": generation_calls,
                "semantic_calls": semantic_calls,
                "spec_calls": spec_calls,
                "total_llm_calls": generation_calls + semantic_calls + spec_calls,
                "solver_calls_per_solved": to_float(config.get("solver_calls_per_solved_problem")),
                "semantic_or_spec_calls_per_solved": (semantic_calls + spec_calls) / solved if solved else None,
                "semantic_parse_success_rate": to_float(config.get("semantic_parse_success_rate")),
                "intended_spec_parse_success_rate": to_float(config.get("intended_spec_parse_success_rate")),
                "parse_success_rate": first_value(
                    to_float(config.get("semantic_parse_success_rate")),
                    to_float(config.get("intended_spec_parse_success_rate")),
                ),
                "semantic_empty_response_count": to_int(config.get("semantic_empty_response_count")),
                "semantic_parse_failed_count": to_int(config.get("semantic_parse_failed_count")),
                "final_error_distribution": config.get("final_error_type_distribution"),
                "max_prompt_chars": max(prompt) if prompt else None,
                "mean_prompt_chars": mean(prompt),
                "max_feedback_chars": max(feedback) if feedback else None,
                "mean_feedback_chars": mean(feedback),
                "expected_objective_leakage": count_true(audit, "prompt_contains_expected_objective")
                + count_true(audit, "feedback_contains_expected_objective"),
                "objective_gap_leakage": count_true(audit, "prompt_contains_objective_gap")
                + count_true(audit, "feedback_contains_objective_gap"),
                "OBJECTIVE_container_count": count_true(audit, "returns_container"),
                "output_contract_no_objective": output_contract_no_objective(audit),
            }
        )
    return rows


def build_band_breakdown(runs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for method, run in runs.items():
        bands = {row.get("problem_id"): row.get("band") or "unknown" for row in run["rounds"]}
        by_band: dict[str, list[dict[str, str]]] = defaultdict(list)
        for problem in run["problems"]:
            by_band[bands.get(problem.get("problem_id"), "unknown")].append(problem)
        for band, problems in sorted(by_band.items()):
            solved = [problem for problem in problems if is_true(problem.get("solved"))]
            rows.append(
                {
                    "method": method,
                    "band": band,
                    "selected_count": len(problems),
                    "solved_count": len(solved),
                    "pass_rate": len(solved) / len(problems) if problems else 0.0,
                    "final_error_distribution": dict(Counter(problem.get("final_error_type") or "unknown" for problem in problems)),
                }
            )
    return rows


def build_solve_overlap(runs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    solved = {
        method: {problem["problem_id"] for problem in run["problems"] if is_true(problem.get("solved"))}
        for method, run in runs.items()
    }
    union_all = set().union(*solved.values()) if solved else set()
    rows: list[dict[str, Any]] = []
    for method, ids in solved.items():
        other = set().union(*(other_ids for other_method, other_ids in solved.items() if other_method != method))
        rows.append({"category": f"solved_by_{method}", "count": len(ids), "problem_ids": sorted(ids)})
        rows.append({"category": f"{method}_only", "count": len(ids - other), "problem_ids": sorted(ids - other)})
    if "original_advisory" in solved and "adaptive_compressed" in solved:
        rows.append(
            {
                "category": "lost_by_adaptive_vs_original",
                "count": len(solved["original_advisory"] - solved["adaptive_compressed"]),
                "problem_ids": sorted(solved["original_advisory"] - solved["adaptive_compressed"]),
            }
        )
    if "original_advisory" in solved and "spec_then_code" in solved:
        rows.append(
            {
                "category": "spec_then_code_only_vs_original",
                "count": len(solved["spec_then_code"] - solved["original_advisory"]),
                "problem_ids": sorted(solved["spec_then_code"] - solved["original_advisory"]),
            }
        )
        rows.append(
            {
                "category": "lost_by_spec_then_code_vs_original",
                "count": len(solved["original_advisory"] - solved["spec_then_code"]),
                "problem_ids": sorted(solved["original_advisory"] - solved["spec_then_code"]),
            }
        )
    rows.append({"category": "solved_by_any_candidate", "count": len(union_all), "problem_ids": sorted(union_all)})
    return rows


def build_error_transitions(runs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for method, run in runs.items():
        counts: Counter[tuple[str, str]] = Counter()
        for problem in run["problems"]:
            trajectory = parse_jsonish(problem.get("error_type_trajectory"), [])
            if not isinstance(trajectory, list):
                continue
            first_valid = to_int(problem.get("first_valid_round"))
            normalized = [normalize_error(value) for value in trajectory]
            if first_valid is not None and first_valid < len(normalized):
                normalized[first_valid] = "solved"
            for before, after in zip(normalized, normalized[1:]):
                counts[(before, after)] += 1
        for (before, after), count in sorted(counts.items()):
            rows.append({"method": method, "transition": f"{before}->{after}", "count": count})
    return rows


def build_cost_tradeoff(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_method = {row["method"]: row for row in rows}
    original = by_method.get("original_advisory")
    output = list(rows)
    if original:
        for method in ("adaptive_compressed", "spec_then_code"):
            candidate = by_method.get(method)
            if not candidate:
                continue
            output.append(
                {
                    "method": f"{method}_vs_original_delta",
                    "solved_count": (candidate.get("solved_count") or 0) - (original.get("solved_count") or 0),
                    "pass_rate": safe_sub(candidate.get("pass_rate"), original.get("pass_rate")),
                    "total_llm_calls": (candidate.get("total_llm_calls") or 0) - (original.get("total_llm_calls") or 0),
                    "max_prompt_chars": safe_sub(candidate.get("max_prompt_chars"), original.get("max_prompt_chars")),
                    "mean_prompt_chars": safe_sub(candidate.get("mean_prompt_chars"), original.get("mean_prompt_chars")),
                    "max_feedback_chars": safe_sub(candidate.get("max_feedback_chars"), original.get("max_feedback_chars")),
                    "mean_feedback_chars": safe_sub(candidate.get("mean_feedback_chars"), original.get("mean_feedback_chars")),
                }
            )
    return output


def render_comparison_md(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Full92 Candidate Comparison",
        "",
        "| Method | Solved | Pass rate | Solver calls | LLM calls | Parse | Max prompt | Max feedback | Leaks | Containers |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['method']} | {row['solved_count']}/{row['selected_problem_count']} | {fmt(row['pass_rate'])} | "
            f"{fmt(row['solver_calls'])} | {fmt(row['total_llm_calls'])} | {fmt(row['parse_success_rate'])} | "
            f"{fmt(row['max_prompt_chars'])} | {fmt(row['max_feedback_chars'])} | "
            f"{fmt(row['expected_objective_leakage'])} | {fmt(row['OBJECTIVE_container_count'])} |"
        )
    return "\n".join(lines) + "\n"


def render_band_md(rows: list[dict[str, Any]]) -> str:
    return "# Full92 Band Breakdown\n\n" + "\n".join(
        render_table(rows, ["method", "band", "selected_count", "solved_count", "pass_rate", "final_error_distribution"])
    ) + "\n"


def render_overlap_md(rows: list[dict[str, Any]]) -> str:
    return "# Full92 Solve Overlap\n\n" + "\n".join(render_table(rows, ["category", "count", "problem_ids"])) + "\n"


def render_transition_md(rows: list[dict[str, Any]]) -> str:
    return "# Full92 Error Transitions\n\n" + "\n".join(render_table(rows, ["method", "transition", "count"])) + "\n"


def render_cost_md(rows: list[dict[str, Any]]) -> str:
    return "# Full92 Cost Tradeoff\n\n" + "\n".join(
        render_table(
            rows,
            [
                "method",
                "solved_count",
                "total_llm_calls",
                "solver_calls_per_solved",
                "semantic_or_spec_calls_per_solved",
                "max_prompt_chars",
                "mean_prompt_chars",
                "max_feedback_chars",
                "mean_feedback_chars",
            ],
        )
    ) + "\n"


def render_table(rows: list[dict[str, Any]], fields: list[str]) -> list[str]:
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(fmt(row.get(field)) for field in fields) + " |")
    return lines


def count_spec_calls(rounds: list[dict[str, str]]) -> int:
    total = 0
    for row in rounds:
        for key in ("intended_spec_parse_success", "extracted_spec_parse_success", "spec_comparison_parse_success"):
            if row.get(key) not in {None, ""}:
                total += 1
    return total


def output_contract_no_objective(audit: list[dict[str, str]]) -> int:
    return sum(
        row.get("final_error_type") == "no_objective"
        and (
            row.get("contains_setObjective") != "True"
            or row.get("contains_optimize") != "True"
            or row.get("has_numeric_objective_output_contract") != "True"
        )
        for row in audit
    )


def count_true(rows: list[dict[str, str]], key: str) -> int:
    return sum(1 for row in rows if is_true(row.get(key)))


def numbers(rows: list[dict[str, str]], key: str) -> list[float]:
    return [value for row in rows if (value := to_float(row.get(key))) is not None]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key)) for key in fields})


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def first(rows: list[dict[str, str]]) -> dict[str, str]:
    return rows[0] if rows else {}


def parse_jsonish(value: Any, default: Any) -> Any:
    if value in {None, ""}:
        return default
    try:
        return json.loads(value) if isinstance(value, str) else value
    except json.JSONDecodeError:
        return default


def normalize_error(value: Any) -> str:
    if value in {None, "", "None"}:
        return "solved"
    return str(value)


def is_true(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


def to_int(value: Any) -> int | None:
    if value in {None, "", "None"}:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    if value in {None, "", "None"}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def safe_sub(left: Any, right: Any) -> float | None:
    left_value = to_float(left)
    right_value = to_float(right)
    if left_value is None or right_value is None:
        return None
    return left_value - right_value


def first_value(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True)
    return str(value)


if __name__ == "__main__":
    main()
