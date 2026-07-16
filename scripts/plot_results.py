"""Generate final report figures from existing experiment outputs only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from src.result_schema import ExperimentResult


DEFAULT_OUT_DIR = EXPERIMENT_ROOT / "outputs" / "final_figures"

FIGURE_BASENAMES = [
    "pass_rate_by_strategy",
    "rounds_to_valid_by_strategy",
    "calls_to_valid_by_strategy",
    "threshold_replay",
    "cost_quality_scatter",
    "gpt5_matched_heatmap",
    "objective_gap_trajectory_examples",
]

# These constants mirror the exact final report numbers. They keep the plotting
# script reproducible without rerunning experiments or depending on mutable output
# folders for the main aggregate figures.
MATCHED_GPT5 = [
    {
        "label": "execution_only",
        "short_label": "Execution",
        "pass_rate": 0.90,
        "rounds_to_valid": 1.333,
        "solver_calls_to_valid": 1.000,
        "semantic_calls_to_valid": 0.000,
    },
    {
        "label": "semantic_execution hard gate",
        "short_label": "Hard gate",
        "pass_rate": 0.60,
        "rounds_to_valid": 2.000,
        "solver_calls_to_valid": 1.000,
        "semantic_calls_to_valid": 1.667,
    },
    {
        "label": "semantic_advisory_execution",
        "short_label": "Advisory",
        "pass_rate": 1.00,
        "rounds_to_valid": 1.700,
        "solver_calls_to_valid": 1.200,
        "semantic_calls_to_valid": 1.200,
    },
]

THRESHOLD_REPLAY = [
    {"threshold": 0.4, "semantic_reject_count": 5, "estimated_solver_calls": 4, "solver_calls_avoided": 5},
    {"threshold": 0.5, "semantic_reject_count": 7, "estimated_solver_calls": 2, "solver_calls_avoided": 7},
    {"threshold": 0.6, "semantic_reject_count": 8, "estimated_solver_calls": 1, "solver_calls_avoided": 8},
]

COST_QUALITY = [
    {
        "label": "GPT-4o exec 20",
        "pass_rate": 0.25,
        "wall_time": 73.27,
        "semantic_calls": 0.0,
    },
    {
        "label": "GPT-4o hard 20",
        "pass_rate": 0.20,
        "wall_time": 102.10,
        "semantic_calls": 3.55,
    },
    {
        "label": "GPT-5 exec 20",
        "pass_rate": 0.45,
        "wall_time": 105.70,
        "semantic_calls": 0.0,
    },
    {
        "label": "GPT-5 hard 20",
        "pass_rate": 0.30,
        "wall_time": 173.50,
        "semantic_calls": 0.60,
    },
    {
        "label": "GPT-5 advisory 10",
        "pass_rate": 1.00,
        "wall_time": 59.98,
        "semantic_calls": 1.20,
    },
]

HEATMAP_PROBLEMS = [f"prob_{index:03d}" for index in range(1, 11)]
HEATMAP_COLUMNS = ["execution_only", "semantic_execution", "semantic_advisory_execution"]
HEATMAP_VALUES = [
    [1, 0, 1],
    [1, 0, 1],
    [1, 1, 1],
    [1, 1, 1],
    [1, 1, 1],
    [1, 0, 1],
    [1, 1, 1],
    [0, 0, 1],
    [1, 1, 1],
    [1, 1, 1],
]

MATCHED_GPT5_RESULT_PATHS = {
    "execution_only": EXPERIMENT_ROOT / "outputs" / "pilot_20260506_205823" / "results.json",
    "semantic_execution": EXPERIMENT_ROOT / "outputs" / "pilot_20260506_210805" / "results.json",
    "semantic_advisory_execution": EXPERIMENT_ROOT / "outputs" / "pilot_20260506_203546" / "results.json",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT_DIR), help="Directory for generated figures.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Create the output directory and print expected filenames without rendering figures.",
    )
    return parser.parse_args(argv)


def expected_figure_paths(out_dir: Path) -> list[Path]:
    return [
        out_dir / f"{basename}{suffix}"
        for basename in FIGURE_BASENAMES
        for suffix in (".png", ".pdf")
    ]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        for path in expected_figure_paths(out_dir):
            print(path)
        return 0

    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    plot_pass_rate(plt, out_dir)
    plot_rounds_to_valid(plt, out_dir)
    plot_calls_to_valid(plt, out_dir)
    plot_threshold_replay(plt, out_dir)
    plot_cost_quality_scatter(plt, out_dir)
    plot_heatmap(plt, ListedColormap, out_dir)
    plot_objective_gap_or_timeline(plt, out_dir)
    write_readme(out_dir)

    print(f"Wrote figures to {out_dir}")
    for path in expected_figure_paths(out_dir):
        print(path)
    print(out_dir / "README.md")
    return 0


def plot_pass_rate(plt: Any, out_dir: Path) -> None:
    labels = [row["short_label"] for row in MATCHED_GPT5]
    values = [row["pass_rate"] for row in MATCHED_GPT5]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    bars = ax.bar(labels, values, color=["#4C78A8", "#F58518", "#54A24B"])
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Pass rate")
    ax.set_title("GPT-5-mini matched 10: pass rate by strategy")
    ax.bar_label(bars, labels=[f"{value:.2f}" for value in values], padding=3)
    ax.text(0.5, -0.22, "Same 10 LogiOR problems: prob_001 to prob_010", transform=ax.transAxes, ha="center")
    save_figure(fig, out_dir, "pass_rate_by_strategy")
    plt.close(fig)


def plot_rounds_to_valid(plt: Any, out_dir: Path) -> None:
    labels = [row["short_label"] for row in MATCHED_GPT5]
    values = [row["rounds_to_valid"] for row in MATCHED_GPT5]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    bars = ax.bar(labels, values, color=["#4C78A8", "#F58518", "#54A24B"])
    ax.set_ylabel("Average rounds to first valid")
    ax.set_title("GPT-5-mini matched 10: convergence rounds")
    ax.bar_label(bars, labels=[f"{value:.3g}" for value in values], padding=3)
    ax.set_ylim(0, max(values) * 1.25)
    save_figure(fig, out_dir, "rounds_to_valid_by_strategy")
    plt.close(fig)


def plot_calls_to_valid(plt: Any, out_dir: Path) -> None:
    labels = [row["short_label"] for row in MATCHED_GPT5]
    solver = [row["solver_calls_to_valid"] for row in MATCHED_GPT5]
    semantic = [row["semantic_calls_to_valid"] for row in MATCHED_GPT5]
    xs = range(len(labels))
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.bar(xs, solver, label="Solver calls", color="#4C78A8")
    ax.bar(xs, semantic, bottom=solver, label="Semantic calls", color="#F58518")
    totals = [a + b for a, b in zip(solver, semantic)]
    for index, total in enumerate(totals):
        ax.text(index, total + 0.05, f"{total:.3g}", ha="center")
    ax.set_xticks(list(xs), labels)
    ax.set_ylabel("Average calls to first valid")
    ax.set_title("GPT-5-mini matched 10: calls to first valid")
    ax.legend()
    ax.set_ylim(0, max(totals) * 1.25)
    save_figure(fig, out_dir, "calls_to_valid_by_strategy")
    plt.close(fig)


def plot_threshold_replay(plt: Any, out_dir: Path) -> None:
    thresholds = [row["threshold"] for row in THRESHOLD_REPLAY]
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.plot(thresholds, [row["semantic_reject_count"] for row in THRESHOLD_REPLAY], marker="o", label="Semantic rejects")
    ax.plot(thresholds, [row["estimated_solver_calls"] for row in THRESHOLD_REPLAY], marker="o", label="Estimated solver calls")
    ax.plot(thresholds, [row["solver_calls_avoided"] for row in THRESHOLD_REPLAY], marker="o", label="Solver calls avoided")
    ax.set_xlabel("Semantic threshold")
    ax.set_ylabel("Count")
    ax.set_title("Semantic threshold replay")
    ax.set_xticks(thresholds)
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    save_figure(fig, out_dir, "threshold_replay")
    plt.close(fig)


def plot_cost_quality_scatter(plt: Any, out_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for row in COST_QUALITY:
        ax.scatter(row["wall_time"], row["pass_rate"], s=70 + 45 * row["semantic_calls"], alpha=0.85)
        ax.annotate(
            row["label"],
            (row["wall_time"], row["pass_rate"]),
            xytext=(6, 5),
            textcoords="offset points",
            fontsize=8.5,
        )
    ax.set_xlabel("Average wall time per problem (seconds)")
    ax.set_ylabel("Pass rate")
    ax.set_title("Cost-quality scatter\nGPT-5 advisory point is n=10; hard-gate points are n=20")
    ax.set_ylim(0, 1.08)
    ax.grid(alpha=0.25)
    save_figure(fig, out_dir, "cost_quality_scatter")
    plt.close(fig)


def plot_heatmap(plt: Any, listed_cmap_cls: Any, out_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 5.4))
    cmap = listed_cmap_cls(["#F2B8A2", "#7AC77B"])
    ax.imshow(HEATMAP_VALUES, cmap=cmap, vmin=0, vmax=1)
    ax.set_xticks(range(len(HEATMAP_COLUMNS)), ["Execution", "Hard gate", "Advisory"], rotation=20, ha="right")
    ax.set_yticks(range(len(HEATMAP_PROBLEMS)), HEATMAP_PROBLEMS)
    ax.set_title("GPT-5-mini matched 10: solved/fail heatmap")
    for row_index, row in enumerate(HEATMAP_VALUES):
        for col_index, value in enumerate(row):
            ax.text(col_index, row_index, "Solved" if value else "Fail", ha="center", va="center", fontsize=8)
    ax.set_xlabel("Strategy")
    ax.set_ylabel("Problem")
    save_figure(fig, out_dir, "gpt5_matched_heatmap")
    plt.close(fig)


def plot_objective_gap_or_timeline(plt: Any, out_dir: Path) -> None:
    selected = ["prob_001", "prob_002", "prob_008"]
    records = load_selected_round_records(selected)
    gap_series = {
        label: [(record["round_index"], record["objective_gap"]) for record in rows if record["objective_gap"] is not None]
        for label, rows in records.items()
    }
    clean_line_possible = all(len(points) >= 2 for points in gap_series.values()) if gap_series else False
    if clean_line_possible:
        plot_objective_gap_lines(plt, out_dir, gap_series)
    else:
        plot_error_timeline(plt, out_dir, records)


def plot_objective_gap_lines(plt: Any, out_dir: Path, gap_series: dict[str, list[tuple[int, float]]]) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.2))
    for label, points in gap_series.items():
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        ax.plot(xs, ys, marker="o", label=label)
    ax.set_xlabel("Round")
    ax.set_ylabel("Objective gap")
    ax.set_title("Objective gap trajectory examples")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)
    save_figure(fig, out_dir, "objective_gap_trajectory_examples")
    plt.close(fig)


def plot_error_timeline(plt: Any, out_dir: Path, records: dict[str, list[dict[str, Any]]]) -> None:
    statuses = sorted({status_for_record(record) for rows in records.values() for record in rows})
    if not statuses:
        statuses = ["missing_data"]
    palette = {
        "valid": "#54A24B",
        "compile_failed": "#B279A2",
        "runtime_error": "#E45756",
        "objective_mismatch": "#F58518",
        "semantic_reject": "#72B7B2",
        "rule_semantic_reject": "#9D755D",
        "llm_failed": "#BAB0AC",
        "missing_data": "#D9D9D9",
        "other": "#4C78A8",
    }
    labels = list(records)
    fig, ax = plt.subplots(figsize=(10, max(4.5, 0.35 * len(labels))))
    for y_index, label in enumerate(labels):
        rows = records[label]
        if not rows:
            ax.scatter([0], [y_index], marker="s", s=120, color=palette["missing_data"])
            continue
        for record in rows:
            status = status_for_record(record)
            ax.scatter(
                [record["round_index"]],
                [y_index],
                marker="s",
                s=120,
                color=palette.get(status, palette["other"]),
            )
            ax.text(record["round_index"], y_index, str(record["round_index"]), ha="center", va="center", fontsize=7)
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xlabel("Round index")
    ax.set_title("Selected GPT-5-mini matched problems: categorical repair timeline")
    handles = [
        plt.Line2D([0], [0], marker="s", color="w", markerfacecolor=palette.get(status, palette["other"]), markersize=9, label=status)
        for status in statuses
    ]
    ax.legend(handles=handles, bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    ax.grid(axis="x", alpha=0.25)
    save_figure(fig, out_dir, "objective_gap_trajectory_examples")
    plt.close(fig)


def load_selected_round_records(problem_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = {}
    for strategy, path in MATCHED_GPT5_RESULT_PATHS.items():
        result = load_result_if_exists(path)
        for problem_id in problem_ids:
            label = f"{problem_id} / {strategy}"
            records[label] = []
            if result is None:
                continue
            problem = next((item for item in result.problems if item.problem_id == problem_id), None)
            if problem is None:
                continue
            for round_result in problem.rounds:
                records[label].append(
                    {
                        "round_index": round_result.round_index,
                        "valid": round_result.valid,
                        "error_type": round_result.error_type,
                        "objective_gap": round_result.objective_gap,
                    }
                )
    return records


def load_result_if_exists(path: Path) -> ExperimentResult | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ExperimentResult.from_dict(payload)


def status_for_record(record: dict[str, Any]) -> str:
    if record.get("valid") is True:
        return "valid"
    error_type = record.get("error_type")
    if isinstance(error_type, str) and error_type:
        return error_type
    return "other"


def save_figure(fig: Any, out_dir: Path, basename: str) -> None:
    fig.tight_layout()
    fig.savefig(out_dir / f"{basename}.png", dpi=200, bbox_inches="tight")
    fig.savefig(out_dir / f"{basename}.pdf", bbox_inches="tight")


def write_readme(out_dir: Path) -> None:
    readme = """# Final Figures

These figures were generated by `scripts/plot_results.py` from existing experiment outputs and exact final report numbers. No new experiments, LLM calls, or solver calls were run.

## Figures

- `pass_rate_by_strategy.png/pdf`: matched GPT-5-mini 10-problem pass rate by strategy.
- `rounds_to_valid_by_strategy.png/pdf`: matched GPT-5-mini 10-problem average rounds to first valid.
- `calls_to_valid_by_strategy.png/pdf`: matched GPT-5-mini 10-problem semantic and solver calls to first valid.
- `threshold_replay.png/pdf`: semantic threshold replay showing reject counts, estimated solver calls, and avoided solver calls.
- `cost_quality_scatter.png/pdf`: pass rate versus wall time. GPT-5 advisory is a 10-problem point; the 20-problem hard-gate points are not sample-matched to it.
- `gpt5_matched_heatmap.png/pdf`: solved/fail heatmap for GPT-5-mini matched 10.
- `objective_gap_trajectory_examples.png/pdf`: objective-gap lines when enough saved gaps exist, otherwise a categorical per-round error timeline for selected problems.

## Notes

The GPT-5 advisory 10 result is sample-matched against the GPT-5 10-problem execution-only and hard-gate baselines. It is not sample-matched against the earlier 20-problem runs. Wall time should be treated as secondary because API latency varies; calls and pass rate are the more stable comparison metrics.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
