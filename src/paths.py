"""Path helpers for the standalone semantic-feedback repair project."""

from __future__ import annotations

import os
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = EXPERIMENT_ROOT
REPO_ROOT = PROJECT_ROOT

LOGIOR_DATASET_ENV = "LOGIOR_DATASET_ROOT"
DATA_ROOT = PROJECT_ROOT / "data"
DEFAULT_LOGIOR_DATASET_ROOT = DATA_ROOT / "raw" / "logior"
ORTHOUGHT_ROOT = DEFAULT_LOGIOR_DATASET_ROOT
HEURIGYM_PIPELINE_ROOT = DATA_ROOT / "raw" / "heurigym"
OUTPUT_ROOT = PROJECT_ROOT / "outputs"


def get_logior_dataset_root(required: bool = False) -> Path | None:
    """Return the configured external LogiOR dataset root.

    The benchmark is intentionally not vendored in this repository. Users can
    point to a local copy with LOGIOR_DATASET_ROOT or pass --dataset-root to
    the public runner.
    """

    configured = os.environ.get(LOGIOR_DATASET_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    if DEFAULT_LOGIOR_DATASET_ROOT.exists():
        return DEFAULT_LOGIOR_DATASET_ROOT.resolve()
    if required:
        raise FileNotFoundError(
            "LogiOR data is not available. Set LOGIOR_DATASET_ROOT to a local "
            "LogiOR/ORThought-compatible dataset path, or pass --dataset-root "
            "to scripts/run_pilot.py. The benchmark data is not included in "
            "this repository."
        )
    return None


def resolve_repo_path(path: str | Path) -> Path:
    """Resolve an absolute path or a path relative to the project root."""

    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate