#!/usr/bin/env python3
"""Offline retrospective gate-policy analysis over V3 convergence logs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


POLICIES = (
    "no_gate",
    "single_should_execute",
    "confidence_threshold",
    "reject_only_high_confidence",
    "static_error_threshold",
    "pessimistic_panel",
    "optimistic_panel",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run_dir", action="append", required=True, help="Run directory with convergence_rounds.jsonl.")
    parser.add_argument("--output_dir", default=None, help="Output directory. Defaults to first run_dir.")
    parser.add_argument("--confidence_threshold", type=float, default=0.7)
    args = parser.parse_args()

    run_dirs = [Path(item) for item in args.run_dir]
    output_dir = Path(args.output_dir) if args.output_dir else run_dirs[0]
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        for row in _read_jsonl(run_dir / "convergence_rounds.jsonl"):
            row.setdefault("run_dir", str(run_dir))
            records.append(row)
    rows = analyze_gate_policies(records, confidence_threshold=args.confidence_threshold)
    _write_csv(output_dir / "gate_policy_summary.csv", rows)
    _write_csv(output_dir / "gate_policy_plot_data.csv", rows)
    (output_dir / "gate_policy_summary.md").write_text(_render_markdown(rows), encoding="utf-8")


def analyze_gate_policies(
    records: list[dict[str, Any]],
    *,
    confidence_threshold: float = 0.7,
) -> list[dict[str, Any]]:
    return [_summarize_policy(policy, records, confidence_threshold) for policy in POLICIES]


def _summarize_policy(
    policy: str,
    records: list[dict[str, Any]],
    confidence_threshold: float,
) -> dict[str, Any]:
    decisions = [_would_execute(policy, row, confidence_threshold) for row in records]
    skipped = [row for row, execute in zip(records, decisions) if not execute]
    executed = [row for row, execute in zip(records, decisions) if execute]
    true_rejection = [row for row in skipped if row.get("valid_solution") is False]
    false_rejection = [row for row in skipped if row.get("valid_solution") is True]
    bad_code = [row for row in records if row.get("valid_solution") is False]
    return {
        "policy": policy,
        "total_rounds": len(records),
        "would_execute": len(executed),
        "would_skip": len(skipped),
        "solver_calls_saved": len(skipped),
        "solver_call_saving_rate": len(skipped) / len(records) if records else 0.0,
        "true_rejection_count": len(true_rejection),
        "false_rejection_count": len(false_rejection),
        "rejection_accuracy": len(true_rejection) / len(skipped) if skipped else None,
        "false_rejection_rate": len(false_rejection)
        / max(1, sum(1 for row in records if row.get("valid_solution") is True)),
        "error_capture_rate": len(true_rejection) / len(bad_code) if bad_code else None,
        "solved_code_false_rejected_count": len(false_rejection),
        "pass_rate_risk_estimate": len(false_rejection)
        / max(1, len({str(row.get("problem_id")) for row in records})),
    }


def _would_execute(policy: str, row: dict[str, Any], confidence_threshold: float) -> bool:
    should_execute = _bool_or_default(row.get("judge_should_execute"), True)
    confidence = _float_or_default(row.get("judge_confidence"), 0.0)
    static_summary = row.get("static_check_summary") if isinstance(row.get("static_check_summary"), dict) else {}
    static_errors = int(static_summary.get("num_errors") or 0)
    by_advisor = row.get("should_execute_by_advisor") if isinstance(row.get("should_execute_by_advisor"), dict) else {}
    if policy == "no_gate":
        return True
    if policy == "single_should_execute":
        return should_execute
    if policy == "confidence_threshold":
        return should_execute and confidence >= confidence_threshold
    if policy == "reject_only_high_confidence":
        if should_execute is False and confidence >= confidence_threshold:
            return False
        return True
    if policy == "static_error_threshold":
        return static_errors <= 0
    if policy == "pessimistic_panel" and by_advisor:
        return all(_bool_or_default(value, True) for value in by_advisor.values())
    if policy == "optimistic_panel" and by_advisor:
        return any(_bool_or_default(value, True) for value in by_advisor.values())
    return should_execute


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _render_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Gate Policy Summary",
        "",
        "| Policy | Total rounds | Would skip | Saving rate | Rejection accuracy | False rejection rate | False rejected solved code |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['policy']} | {row['total_rounds']} | {row['would_skip']} | "
            f"{_fmt(row.get('solver_call_saving_rate'))} | {_fmt(row.get('rejection_accuracy'))} | "
            f"{_fmt(row.get('false_rejection_rate'))} | {row.get('solved_code_false_rejected_count')} |"
        )
    lines.extend(
        [
            "",
            "Interpretation:",
            "- Hard gating remains unsafe unless false rejection is low and solved-code false rejections are acceptable.",
            "- Prefer retrospective analysis until the gate policy is calibrated on a larger held-out set.",
        ]
    )
    return "\n".join(lines) + "\n"


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.3f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(value)


def _bool_or_default(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in {"true", "1", "yes"}:
            return True
        if value.lower() in {"false", "0", "no"}:
            return False
    return default


def _float_or_default(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    main()
