#!/usr/bin/env python3
"""Compare V3 medium repair candidates against existing medium references."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = Path("outputs/v3_module_medium_comparison")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline_run_dir", required=True)
    parser.add_argument("--original_run_dir", required=True)
    parser.add_argument("--adaptive_run_dir", required=True)
    parser.add_argument("--spec_then_code_run_dir", required=True)
    parser.add_argument("--multi_advisor_run_dir", required=True)
    parser.add_argument("--output_dir", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    runs = {
        "baseline": Path(args.baseline_run_dir),
        "original_advisory": Path(args.original_run_dir),
        "adaptive_compressed": Path(args.adaptive_run_dir),
        "spec_then_code": Path(args.spec_then_code_run_dir),
        "multi_advisor_disagreement": Path(args.multi_advisor_run_dir),
    }
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data = {name: load_run(name, path) for name, path in runs.items()}

    comparison = build_comparison(data)
    band_rows = build_band_breakdown(data)
    transition_rows = build_error_transitions(data)
    cost_rows = build_cost_tradeoff(data)
    overlap_rows = build_solve_overlap(data)

    write_csv(output_dir / "medium_candidate_comparison.csv", comparison)
    write_csv(output_dir / "medium_candidate_band_breakdown.csv", band_rows)
    write_csv(output_dir / "medium_candidate_error_transitions.csv", transition_rows)
    write_csv(output_dir / "medium_candidate_cost_tradeoff.csv", cost_rows)
    write_csv(output_dir / "medium_candidate_solve_overlap.csv", overlap_rows)

    (output_dir / "medium_candidate_comparison.md").write_text(render_comparison_md(comparison), encoding="utf-8")
    (output_dir / "medium_candidate_band_breakdown.md").write_text(render_band_md(band_rows), encoding="utf-8")
    (output_dir / "medium_candidate_error_transitions.md").write_text(render_transition_md(transition_rows), encoding="utf-8")
    (output_dir / "medium_candidate_cost_tradeoff.md").write_text(render_cost_md(cost_rows), encoding="utf-8")
    (output_dir / "medium_candidate_solve_overlap.md").write_text(render_overlap_md(overlap_rows), encoding="utf-8")
    print(f"Wrote medium candidate comparison to {output_dir}")


def load_run(name: str, run_dir: Path) -> dict[str, Any]:
    return {
        "name": name,
        "run_dir": str(run_dir),
        "config": first_row(read_csv(run_dir / "per_config_summary.csv")),
        "problems": read_csv(run_dir / "per_problem_summary.csv"),
        "rounds": read_csv(run_dir / "per_round_metrics.csv"),
        "audit": read_csv(run_dir / "expanded_artifact_audit.csv"),
        "selected": read_json(run_dir / "selected_problems.json"),
    }


def build_comparison(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for name, run in data.items():
        config = run["config"]
        problems = run["problems"]
        audit = run["audit"]
        spec_calls = count_spec_calls(run["rounds"])
        semantic_calls = to_int(config.get("total_semantic_calls")) or 0
        parse_success_rate = first_not_none(
            to_float(config.get("semantic_parse_success_rate")),
            to_float(config.get("intended_spec_parse_success_rate")),
        )
        solved_ids = [str(row.get("problem_id")) for row in problems if is_true(row.get("solved"))]
        prompt_chars = numeric_values(audit, "repair_prompt_char_count")
        feedback_chars = numeric_values(audit, "feedback_char_count")
        rows.append(
            {
                "method": name,
                "run_dir": run["run_dir"],
                "selected_problem_count": to_int(config.get("total_problems")),
                "solved_count": to_int(config.get("solved_count")),
                "pass_rate": to_float(config.get("pass_rate")),
                "solved_problem_ids": solved_ids,
                "avg_first_valid_round": to_float(config.get("average_first_valid_round_among_solved")),
                "median_first_valid_round": to_float(config.get("median_first_valid_round_among_solved")),
                "solver_calls": to_int(config.get("total_solver_calls")),
                "generation_calls": to_int(config.get("total_llm_generation_calls")),
                "semantic_calls": semantic_calls,
                "spec_calls": spec_calls,
                "total_llm_calls": (to_int(config.get("total_llm_generation_calls")) or 0) + semantic_calls + spec_calls,
                "solver_calls_per_solved": to_float(config.get("solver_calls_per_solved_problem")),
                "semantic_or_spec_calls_per_solved": semantic_or_spec_per_solved(config, semantic_calls, spec_calls),
                "parse_success_rate": parse_success_rate,
                "semantic_parse_success_rate": to_float(config.get("semantic_parse_success_rate")),
                "intended_spec_parse_success_rate": to_float(config.get("intended_spec_parse_success_rate")),
                "final_error_distribution": config.get("final_error_type_distribution"),
                "max_prompt_chars": max(prompt_chars) if prompt_chars else None,
                "mean_prompt_chars": mean(prompt_chars),
                "max_feedback_chars": max(feedback_chars) if feedback_chars else None,
                "mean_feedback_chars": mean(feedback_chars),
                "expected_objective_leakage": count_true(audit, "prompt_contains_expected_objective")
                + count_true(audit, "feedback_contains_expected_objective"),
                "objective_gap_leakage": count_true(audit, "prompt_contains_objective_gap")
                + count_true(audit, "feedback_contains_objective_gap"),
                "OBJECTIVE_container_count": count_true(audit, "returns_container"),
                "output_contract_no_objective": output_contract_no_objective(audit),
                "advisor_count": to_float(config.get("advisor_count")),
                "should_execute_disagreement_rate": to_float(config.get("should_execute_disagreement_rate")),
            }
        )
    return rows


def build_band_breakdown(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, run in data.items():
        bands = {str(row.get("problem_id")): str(row.get("band") or "unknown") for row in run["rounds"] if row.get("problem_id")}
        problems_by_band: dict[str, list[dict[str, str]]] = defaultdict(list)
        for problem in run["problems"]:
            problems_by_band[bands.get(str(problem.get("problem_id")), "unknown")].append(problem)
        for band, problems in sorted(problems_by_band.items()):
            solved = [row for row in problems if is_true(row.get("solved"))]
            final_errors = Counter(str(row.get("final_error_type") or "unknown") for row in problems)
            rows.append(
                {
                    "method": name,
                    "band": band,
                    "selected_count": len(problems),
                    "solved_count": len(solved),
                    "pass_rate": len(solved) / len(problems) if problems else 0.0,
                    "final_error_distribution": dict(final_errors),
                }
            )
    return rows


def build_error_transitions(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, run in data.items():
        counts: Counter[tuple[str, str]] = Counter()
        for problem in run["problems"]:
            trajectory = parse_jsonish(problem.get("error_type_trajectory"), [])
            first = normalize_error(trajectory[0] if trajectory else None)
            second = normalize_error(trajectory[1] if len(trajectory) > 1 else None)
            counts[(first, second)] += 1
        for (from_error, to_error), count in sorted(counts.items()):
            rows.append(
                {
                    "method": name,
                    "round0_error": from_error,
                    "round1_error": to_error,
                    "transition": f"{from_error}->{to_error}",
                    "count": count,
                    "repeated_failure": from_error == to_error and from_error != "solved",
                }
            )
    return rows


def build_cost_tradeoff(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = build_comparison(data)
    by_method = {row["method"]: row for row in rows}
    original = by_method.get("original_advisory")
    for method in ("adaptive_compressed", "spec_then_code", "multi_advisor_disagreement"):
        candidate = by_method.get(method)
        if original and candidate:
            solved_delta = (to_int(candidate.get("solved_count")) or 0) - (to_int(original.get("solved_count")) or 0)
            call_delta = (to_int(candidate.get("total_llm_calls")) or 0) - (to_int(original.get("total_llm_calls")) or 0)
            rows.append(
                {
                    "method": f"{method}_vs_original_delta",
                    "solved_count": solved_delta,
                    "pass_rate": safe_sub(candidate.get("pass_rate"), original.get("pass_rate")),
                    "total_llm_calls": call_delta,
                    "extra_llm_calls_per_additional_solve": call_delta / solved_delta if solved_delta > 0 else None,
                    "max_prompt_chars": safe_sub(candidate.get("max_prompt_chars"), original.get("max_prompt_chars")),
                    "mean_prompt_chars": safe_sub(candidate.get("mean_prompt_chars"), original.get("mean_prompt_chars")),
                    "max_feedback_chars": safe_sub(candidate.get("max_feedback_chars"), original.get("max_feedback_chars")),
                    "mean_feedback_chars": safe_sub(candidate.get("mean_feedback_chars"), original.get("mean_feedback_chars")),
                }
            )
    return rows


def build_solve_overlap(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    solved = {
        name: {str(row.get("problem_id")) for row in run["problems"] if is_true(row.get("solved"))}
        for name, run in data.items()
    }
    original_or_adaptive = solved.get("original_advisory", set()) | solved.get("adaptive_compressed", set())
    rows = []
    for method, ids in sorted(solved.items()):
        rows.append({"category": f"solved_by_{method}", "count": len(ids), "problem_ids": sorted(ids)})
    for method in ("spec_then_code", "multi_advisor_disagreement"):
        ids = solved.get(method, set())
        rows.append({"category": f"{method}_only_vs_original_adaptive", "count": len(ids - original_or_adaptive), "problem_ids": sorted(ids - original_or_adaptive)})
        rows.append({"category": f"lost_by_{method}_vs_original_adaptive", "count": len(original_or_adaptive - ids), "problem_ids": sorted(original_or_adaptive - ids)})
    return rows


def render_comparison_md(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Medium Candidate Comparison",
        "",
        "| Method | Solved | Pass rate | Solver calls | LLM calls | Parse | Max prompt | Max feedback | Leaks | Containers |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['method']} | {row.get('solved_count')}/{row.get('selected_problem_count')} | "
            f"{fmt(row.get('pass_rate'))} | {row.get('solver_calls')} | {row.get('total_llm_calls')} | "
            f"{fmt(row.get('parse_success_rate'))} | {fmt(row.get('max_prompt_chars'))} | "
            f"{fmt(row.get('max_feedback_chars'))} | {row.get('expected_objective_leakage')} | "
            f"{row.get('OBJECTIVE_container_count')} |"
        )
    return "\n".join(lines) + "\n"


def render_band_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Medium Candidate Band Breakdown", "", "| Method | Band | Selected | Solved | Pass rate | Final errors |", "|---|---|---:|---:|---:|---|"]
    for row in rows:
        lines.append(
            f"| {row['method']} | {row['band']} | {row['selected_count']} | {row['solved_count']} | "
            f"{fmt(row['pass_rate'])} | {json.dumps(row['final_error_distribution'], sort_keys=True)} |"
        )
    return "\n".join(lines) + "\n"


def render_transition_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Medium Candidate Error Transitions", "", "| Method | Transition | Count | Repeated failure |", "|---|---|---:|---|"]
    for row in rows:
        lines.append(f"| {row['method']} | `{row['transition']}` | {row['count']} | {row['repeated_failure']} |")
    return "\n".join(lines) + "\n"


def render_cost_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Medium Candidate Cost Tradeoff", "", "| Method | Solved delta/solved | LLM calls | Max prompt delta/chars | Max feedback delta/chars |", "|---|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(
            f"| {row['method']} | {row.get('solved_count')} | {row.get('total_llm_calls')} | "
            f"{fmt(row.get('max_prompt_chars'))} | {fmt(row.get('max_feedback_chars'))} |"
        )
    return "\n".join(lines) + "\n"


def render_overlap_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Medium Candidate Solve Overlap", "", "| Category | Count | Problems |", "|---|---:|---|"]
    for row in rows:
        lines.append(f"| {row['category']} | {row['count']} | {', '.join(row['problem_ids'])} |")
    return "\n".join(lines) + "\n"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key)) for key in fieldnames})


def first_row(rows: list[dict[str, str]]) -> dict[str, str]:
    return rows[0] if rows else {}


def count_spec_calls(rounds: list[dict[str, str]]) -> int:
    total = 0
    for row in rounds:
        if row.get("intended_spec_parse_success") not in {None, ""}:
            total += 1
        if row.get("extracted_spec_parse_success") not in {None, ""}:
            total += 1
        if row.get("spec_comparison_parse_success") not in {None, ""}:
            total += 1
    return total


def semantic_or_spec_per_solved(config: dict[str, str], semantic_calls: int, spec_calls: int) -> float | None:
    solved = to_int(config.get("solved_count")) or 0
    return (semantic_calls + spec_calls) / solved if solved else None


def numeric_values(rows: list[dict[str, str]], key: str) -> list[float]:
    values = [to_float(row.get(key)) for row in rows]
    return [value for value in values if value is not None]


def count_true(rows: list[dict[str, str]], key: str) -> int:
    return sum(1 for row in rows if is_true(row.get(key)))


def output_contract_no_objective(audit: list[dict[str, str]]) -> int:
    return sum(
        1
        for row in audit
        if str(row.get("final_error_type") or "") == "no_objective"
        and str(row.get("objective_output_issue") or "") != "none_detected"
    )


def parse_jsonish(value: Any, default: Any) -> Any:
    if value in {None, ""}:
        return default
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return default


def normalize_error(value: Any) -> str:
    if value in {None, "", "None"}:
        return "solved"
    return str(value)


def first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def safe_sub(a: Any, b: Any) -> float | None:
    left = to_float(a)
    right = to_float(b)
    if left is None or right is None:
        return None
    return left - right


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def to_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.3f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(value)


if __name__ == "__main__":
    main()
