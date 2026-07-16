#!/usr/bin/env python3
"""Offline heuristic feedback-uptake analysis from existing V3 artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from src.feedback_uptake import evaluate_feedback_uptake, summarize_feedback_uptake


DEFAULT_OUTPUT = Path("outputs/v3_adaptive_medium_pilot/analysis/feedback_uptake")


class HeuristicConfig:
    feedback_uptake_mode = "heuristic"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run_dir", action="append", required=True)
    parser.add_argument("--label", action="append", default=None)
    parser.add_argument("--output_dir", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    run_dirs = [Path(item) for item in args.run_dir]
    labels = args.label or [path.name for path in run_dirs]
    if len(labels) != len(run_dirs):
        raise ValueError("--label count must match --run_dir count.")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, Any]] = []
    for label, run_dir in zip(labels, run_dirs):
        items.extend(analyze_run(label, run_dir))
    summary_rows = summarize_items(items)
    by_type_rows = summarize_by_error_type(items)

    write_csv(output_dir / "feedback_uptake_items.csv", items)
    write_csv(output_dir / "feedback_uptake_summary.csv", summary_rows)
    write_csv(output_dir / "feedback_uptake_by_error_type.csv", by_type_rows)
    (output_dir / "feedback_uptake_summary.md").write_text(
        render_summary_md(summary_rows, by_type_rows),
        encoding="utf-8",
    )
    print(f"Wrote feedback uptake analysis to {output_dir}")


def analyze_run(label: str, run_dir: Path) -> list[dict[str, Any]]:
    outcomes = load_problem_outcomes(run_dir)
    rows: list[dict[str, Any]] = []
    for problem_dir in sorted(path for path in run_dir.iterdir() if path.is_dir() and path.name.startswith("prob_")):
        problem_id = problem_dir.name
        round_dirs = sorted(path for path in problem_dir.glob("round_*") if path.is_dir())
        for current_round, next_round in zip(round_dirs, round_dirs[1:]):
            current_index = parse_round_index(current_round.name)
            previous_advisory = read_json(current_round / "semantic_feedback.json")
            previous_code = read_text(current_round / "extracted_code.py")
            next_code = read_text(next_round / "extracted_code.py")
            execution_before = execution_summary(read_json(current_round / "metadata.json"))
            execution_after = execution_summary(read_json(next_round / "metadata.json"))
            eventual_solved = outcomes.get(problem_id, {}).get("solved")
            diagnosis = extract_diagnosis(previous_advisory)
            diagnosed_errors = diagnosis.get("diagnosed_errors") if isinstance(diagnosis, dict) else []
            if isinstance(diagnosed_errors, list):
                for error in diagnosed_errors:
                    if not isinstance(error, dict):
                        continue
                    fix = str(error.get("suggested_fix") or error.get("description") or "").strip()
                    if not fix:
                        continue
                    uptake = evaluate_feedback_uptake(
                        {"repair_instructions": [fix]},
                        previous_code,
                        next_code,
                        "",
                        execution_before,
                        execution_after,
                        HeuristicConfig(),
                        problem_id=problem_id,
                        round_from=current_index,
                        eventual_solved=eventual_solved,
                    )
                    for item in uptake:
                        row = item.to_dict()
                        row.update(
                            {
                                "method": label,
                                "run_dir": str(run_dir),
                                "diagnosed_error_type": str(error.get("type") or "other"),
                                "severity": str(error.get("severity") or ""),
                                "evidence_snippet": str(error.get("evidence") or "")[:240],
                            }
                        )
                        rows.append(row)
            instructions = diagnosis.get("repair_instructions") if isinstance(diagnosis, dict) else []
            if isinstance(instructions, list):
                uptake = evaluate_feedback_uptake(
                    {"repair_instructions": [str(item) for item in instructions if str(item).strip()]},
                    previous_code,
                    next_code,
                    "",
                    execution_before,
                    execution_after,
                    HeuristicConfig(),
                    problem_id=problem_id,
                    round_from=current_index,
                    eventual_solved=eventual_solved,
                )
                for item in uptake:
                    row = item.to_dict()
                    row.update(
                        {
                            "method": label,
                            "run_dir": str(run_dir),
                            "diagnosed_error_type": "repair_instruction",
                            "severity": "",
                            "evidence_snippet": "",
                        }
                    )
                    rows.append(row)
    return rows


def summarize_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by_method[str(item.get("method"))].append(item)
    rows: list[dict[str, Any]] = []
    for method, method_items in sorted(by_method.items()):
        summary = summarize_feedback_uptake(method_items)
        summary.update(
            {
                "method": method,
                "known_implementation_items": sum(
                    1 for item in method_items if item.get("implemented_next_round") is not None
                ),
                "known_resolution_items": sum(1 for item in method_items if item.get("error_resolved") is not None),
            }
        )
        rows.append(summary)
    return rows


def summarize_by_error_type(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[(str(item.get("method")), str(item.get("diagnosed_error_type")))].append(item)
    rows: list[dict[str, Any]] = []
    for (method, error_type), group in sorted(grouped.items()):
        summary = summarize_feedback_uptake(group)
        summary.update({"method": method, "diagnosed_error_type": error_type})
        rows.append(summary)
    return rows


def render_summary_md(summary_rows: list[dict[str, Any]], by_type_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Offline Feedback Uptake Summary",
        "",
        "| Method | Items | Implementation rate | Resolution rate | New error rate | Gap improvement rate | Implemented+solved |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['method']} | {row['feedback_items_total']} | {fmt(row.get('implementation_rate'))} | "
            f"{fmt(row.get('resolution_rate'))} | {fmt(row.get('new_error_rate'))} | "
            f"{fmt(row.get('objective_gap_improvement_rate'))} | {row.get('implemented_and_solved_count')} |"
        )
    lines.extend(
        [
            "",
            "## Uptake By Diagnosed Error Type",
            "",
            "| Method | Error type | Items | Implementation rate | Resolution rate |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for row in by_type_rows:
        lines.append(
            f"| {row['method']} | {row['diagnosed_error_type']} | {row['feedback_items_total']} | "
            f"{fmt(row.get('implementation_rate'))} | {fmt(row.get('resolution_rate'))} |"
        )
    lines.extend(
        [
            "",
            "Note: this is heuristic offline uptake. Treat it as directional evidence, not a substitute for human artifact review.",
        ]
    )
    return "\n".join(lines) + "\n"


def extract_diagnosis(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    diagnosis = payload.get("advisory_diagnosis")
    if isinstance(diagnosis, dict):
        return diagnosis
    return payload


def execution_summary(metadata: Any) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    return {
        "error_type": metadata.get("error_type"),
        "objective_gap": metadata.get("objective_gap"),
    }


def load_problem_outcomes(run_dir: Path) -> dict[str, dict[str, Any]]:
    rows = read_csv(run_dir / "per_problem_summary.csv")
    return {
        str(row.get("problem_id")): {
            "solved": str(row.get("solved")).lower() == "true",
            "final_error_type": row.get("final_error_type"),
        }
        for row in rows
        if row.get("problem_id")
    }


def parse_round_index(name: str) -> int:
    try:
        return int(name.split("_", 1)[1])
    except (IndexError, ValueError):
        return 0


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.3f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(value)


if __name__ == "__main__":
    main()
