"""Read-only LogiOR/ORThought-compatible data adapter.

The adapter loads problem text and metadata from a local benchmark directory
provided through LOGIOR_DATASET_ROOT, a config field, or --dataset-root. It does
not import benchmark modules, run external scripts, or modify dataset files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import LOGIOR_DATASET_ENV, get_logior_dataset_root


DATASET_ALIASES = {
    "logior": "LogiOR",
    "nlp4lp": "NLP4LP",
    "complexor": "ComplexOR",
    "industryor": "IndustryOR",
}


@dataclass(frozen=True, slots=True)
class ORThoughtAdapter:
    dataset_name: str = "logior"
    orthought_root: Path | None = None
    dataset_root: Path | None = None

    @property
    def root(self) -> Path:
        configured = self.dataset_root or self.orthought_root or get_logior_dataset_root(required=True)
        return Path(configured).expanduser().resolve()

    @property
    def canonical_dataset_name(self) -> str:
        return DATASET_ALIASES.get(self.dataset_name.lower(), self.dataset_name)

    def load_problems(self, limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
        summary = self._load_summary()
        problem_dirs = self._problem_dirs()
        if not problem_dirs and not summary:
            self.print_discovery()
            raise FileNotFoundError(
                f"No LogiOR-compatible problem data found for dataset {self.dataset_name!r} under {self.root}. "
                f"Set {LOGIOR_DATASET_ENV} or pass --dataset-root to a directory containing prob_* folders, "
                "datasets/processed/<Dataset>, or processed/<Dataset>."
            )

        problem_ids = sorted(set(summary) | {path.name for path in problem_dirs})

        problems: list[dict[str, Any]] = []
        dirs_by_id = {path.name: path for path in problem_dirs}
        for problem_id in problem_ids:
            problem_dir = dirs_by_id.get(problem_id)
            summary_item = summary.get(problem_id, {})
            problem_text = self._read_problem_text(problem_dir, summary_item)
            if not problem_text:
                continue

            metadata = self._metadata_for(problem_id, problem_dir, summary_item)
            problems.append(
                {
                    "problem_id": problem_id,
                    "dataset_name": self.dataset_name.lower(),
                    "problem_text": problem_text,
                    "metadata": metadata,
                }
            )
        problems.sort(
            key=lambda problem: (
                self._difficulty_score(problem["metadata"].get("summary", {})),
                str(problem["problem_id"]),
            )
        )
        for rank, problem in enumerate(problems):
            problem["metadata"]["difficulty_rank"] = rank
        if offset > 0:
            problems = problems[offset:]
        if limit is not None:
            problems = problems[:limit]
        return problems

    def sample_problem_ids(self, limit: int = 5) -> list[str]:
        return [problem["problem_id"] for problem in self.load_problems(limit=limit)]

    def discover_candidate_files(self) -> dict[str, list[str]]:
        dataset_dir_candidates = [str(path) for path in self._dataset_dir_candidates()]
        summary_candidates = [str(path) for path in self._summary_candidates()]
        existing_problem_dirs: list[str] = []
        for candidate in self._dataset_dir_candidates():
            if candidate.is_dir():
                existing_problem_dirs.extend(str(path) for path in sorted(candidate.glob("prob_*"))[:10])
        return {
            "dataset_dir_candidates": dataset_dir_candidates,
            "summary_candidates": summary_candidates,
            "sample_problem_dirs": existing_problem_dirs,
        }

    def print_discovery(self) -> None:
        print("LogiOR candidate files:")
        for label, paths in self.discover_candidate_files().items():
            print(f"  {label}:")
            for path in paths:
                print(f"    - {path}")

    def generate_formulation(self, problem: dict[str, Any], strategy: str) -> str:
        del problem, strategy
        raise NotImplementedError("Generation is handled by src.llm_client.")

    def _problem_dirs(self) -> list[Path]:
        for candidate in self._dataset_dir_candidates():
            if candidate.is_dir():
                return sorted(
                    [path for path in candidate.iterdir() if path.is_dir() and path.name.startswith("prob_")],
                    key=lambda path: path.name,
                )
        return []

    def _dataset_dir_candidates(self) -> list[Path]:
        name = self.canonical_dataset_name
        lower = self.dataset_name.lower()
        root = self.root
        return [
            root,
            root / name,
            root / lower,
            root / "datasets" / "processed" / name,
            root / "datasets" / "processed" / lower,
            root / "processed" / name,
            root / "processed" / lower,
        ]

    def _summary_candidates(self) -> list[Path]:
        lower = self.dataset_name.lower()
        root = self.root
        return [
            root / f"summary_{lower}.json",
            root / "datasets" / "summary" / f"summary_{lower}.json",
            root / "summary" / f"summary_{lower}.json",
            root.parent / "summary" / f"summary_{lower}.json",
        ]

    def _load_summary(self) -> dict[str, dict[str, Any]]:
        for candidate in self._summary_candidates():
            if not candidate.is_file():
                continue
            with candidate.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, dict):
                return {
                    str(problem_id): item
                    for problem_id, item in payload.items()
                    if isinstance(item, dict)
                }
        return {}

    def _read_problem_text(self, problem_dir: Path | None, summary_item: dict[str, Any]) -> str:
        if problem_dir is not None:
            question_path = problem_dir / "question.txt"
            if question_path.is_file():
                return question_path.read_text(encoding="utf-8").strip()
        description = summary_item.get("description")
        return str(description).strip() if description is not None else ""

    def _metadata_for(
        self,
        problem_id: str,
        problem_dir: Path | None,
        summary_item: dict[str, Any],
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "problem_id": problem_id,
            "dataset_name": self.dataset_name.lower(),
            "canonical_dataset_name": self.canonical_dataset_name,
            "dataset_root": str(self.root),
        }
        if problem_dir is not None:
            metadata["problem_dir"] = str(problem_dir)
            answer_path = problem_dir / "answer.json"
            if answer_path.is_file():
                metadata["answer_path"] = str(answer_path)
                try:
                    metadata["answer"] = json.loads(answer_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    metadata["answer_parse_error"] = str(exc)
            for name in ("question.txt", "model.txt", "code.py"):
                path = problem_dir / name
                if path.is_file():
                    metadata[f"{path.stem}_path"] = str(path)
        if summary_item:
            metadata["summary"] = summary_item
        return metadata

    def _difficulty_score(self, summary_item: dict[str, Any]) -> float:
        details = summary_item.get("details", {})
        if not isinstance(details, dict):
            return float("inf")
        variables = details.get("variables_num")
        constraints = details.get("constraints_num")
        if variables is None or constraints is None:
            return float("inf")
        try:
            return float(variables) + float(constraints)
        except (TypeError, ValueError):
            return float("inf")