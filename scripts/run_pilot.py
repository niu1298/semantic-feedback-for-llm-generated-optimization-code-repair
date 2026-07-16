"""Run a dry-run or Phase 2A vanilla generation pilot."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from src.config import load_config
from src.paths import (
    EXPERIMENT_ROOT as RESOLVED_EXPERIMENT_ROOT,
    HEURIGYM_PIPELINE_ROOT,
    ORTHOUGHT_ROOT,
    LOGIOR_DATASET_ENV,
    OUTPUT_ROOT,
    REPO_ROOT,
)
from src.strategy_runner import StrategyRunner
from src.visualization_exports import export_run_visualizations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to a pilot YAML config.")
    parser.add_argument("--dry-run", action="store_true", help="Write placeholder results without LLM calls.")
    parser.add_argument("--problem_limit", type=int, default=None, help="Override the config problem limit.")
    parser.add_argument("--strategy", default=None, help="Override the config strategy.")
    parser.add_argument(
        "--dataset-root",
        default=None,
        help="Path to local LogiOR/ORThought-compatible benchmark data. Overrides LOGIOR_DATASET_ROOT.",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    args = parse_args()
    config = load_config(args.config).with_overrides(
        problem_limit=args.problem_limit,
        strategy=args.strategy,
        dataset_root=args.dataset_root,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = config.output_dir / f"pilot_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    os.environ["COST_RUN_ID"] = run_dir.name
    os.environ["COST_CONFIG_NAME"] = Path(args.config).stem

    print("Resolved paths:")
    print(f"  REPO_ROOT: {REPO_ROOT}")
    dataset_root_display = config.dataset_root or f"set {LOGIOR_DATASET_ENV} or pass --dataset-root"
    print(f"  DATASET_ROOT: {dataset_root_display}")
    print(f"  HEURIGYM_PIPELINE_ROOT: {HEURIGYM_PIPELINE_ROOT}")
    print(f"  EXPERIMENT_ROOT: {RESOLVED_EXPERIMENT_ROOT}")
    print(f"  OUTPUT_ROOT: {OUTPUT_ROOT}")
    print(f"  RUN_DIR: {run_dir}")
    print("Strategies:")
    for strategy in config.strategies:
        print(f"  - {strategy}")
    print(f"Mode: {'dry-run placeholder' if args.dry_run else config.strategy}")

    runner = StrategyRunner(config)
    if args.dry_run:
        result = runner.run_placeholder()
    else:
        result = runner.run_real(run_dir)

    results_path = run_dir / "results.json"
    results_path.write_text(result.to_json(), encoding="utf-8")
    print(f"Wrote results: {results_path}")
    exported = export_run_visualizations(result, run_dir)
    print(f"Wrote trend records: {exported['trend_records']}")
    print(f"Wrote problem summary: {exported['problem_summary']}")
    print(f"Wrote run summary: {exported['run_summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
