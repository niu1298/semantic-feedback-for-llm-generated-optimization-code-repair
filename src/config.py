"""Configuration loading for pilot feedback efficiency runs."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .paths import resolve_repo_path


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    problem_source: str
    dataset_name: str
    problem_limit: int
    strategy: str
    llm_provider: str
    llm_model: str
    semantic_provider: str | None
    semantic_model: str | None
    request_timeout_seconds: int
    max_retries: int
    max_tokens: int
    temperature: float | None
    thinking: str
    output_dir: Path
    dataset_root: Path | None = None
    reasoning_effort: str | None = None
    experiment_name: str | None = None
    problem_offset: int = 0
    problem_ids: list[str] | None = None
    max_problems_per_band: int | None = None
    random_seed: int | None = None
    max_rounds: int = 1
    strategies: list[str] = field(default_factory=list)
    semantic_max_tokens: int | None = None
    semantic_prompt_style: str = "default"
    semantic_threshold: float | None = None
    semantic_fast_provider: str | None = None
    semantic_fast_model: str | None = None
    semantic_strong_provider: str | None = None
    semantic_strong_model: str | None = None
    semantic_cascade_enabled: bool = False
    semantic_low_threshold: float = 0.4
    semantic_high_threshold: float = 0.75
    solver_timeout_seconds: int | None = None
    use_expected_objective_in_repair: bool = True
    mask_expected_objective: bool = False
    advisory_mode: str | None = None
    static_checks_enabled: bool = True
    include_static_checks_in_advisor_prompt: bool = True
    include_static_checks_in_repair_prompt: bool | None = None
    include_semantic_diagnosis_in_repair_prompt: bool | None = None
    include_execution_feedback_in_repair_prompt: bool = True
    convergence_logging_enabled: bool = True
    use_formulation_spec: bool = False
    spec_provider: str | None = None
    spec_model: str | None = None
    spec_max_tokens: int | None = None
    spec_prompt_style: str = "full"
    include_formulation_spec_in_codegen: bool = False
    include_formulation_spec_in_repair: bool = False
    use_code_to_spec: bool = False
    code_spec_provider: str | None = None
    code_spec_model: str | None = None
    code_spec_max_tokens: int | None = None
    code_spec_prompt_style: str = "full"
    include_extracted_spec_in_repair: bool = False
    use_spec_comparison_diagnosis: bool = False
    spec_comparison_provider: str | None = None
    spec_comparison_model: str | None = None
    spec_comparison_max_tokens: int | None = None
    include_spec_comparison_in_repair: bool = False
    semantic_diagnosis_sources: list[str] = field(default_factory=lambda: ["direct_code"])
    feedback_uptake_enabled: bool = False
    feedback_uptake_mode: str = "off"
    feedback_uptake_provider: str | None = None
    feedback_uptake_model: str | None = None
    feedback_uptake_max_tokens: int | None = None
    advisor_models: list[dict[str, Any]] = field(default_factory=list)
    advisor_aggregation: str = "single"
    repair_feedback_max_chars: int | None = None
    repair_feedback_max_items: int | None = None
    compress_semantic_feedback: bool = False
    compression_policy: str = "fixed"
    adaptive_repair_feedback_max_chars: int | None = None
    adaptive_repair_feedback_max_items: int | None = None
    preserve_all_missing_constraint: bool = False
    preserve_all_wrong_objective: bool = False
    preserve_variable_and_constraint_names: bool = False
    preserve_one_freeform_instruction: bool = False
    preserve_error_type_conditioned_feedback: bool = False
    semantic_feedback_priority_order: list[str] = field(
        default_factory=lambda: [
            "missing_constraint",
            "wrong_objective",
            "domain_issue",
            "output_issue",
            "api_issue",
            "runtime_risk",
            "other",
        ]
    )
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not self.strategies:
            object.__setattr__(self, "strategies", [self.strategy])

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "problem_source": self.problem_source,
            "dataset_name": self.dataset_name,
            "dataset_root": str(self.dataset_root) if self.dataset_root is not None else None,
            "problem_limit": self.problem_limit,
            "problem_offset": self.problem_offset,
            "problem_ids": list(self.problem_ids) if self.problem_ids is not None else None,
            "max_problems_per_band": self.max_problems_per_band,
            "random_seed": self.random_seed,
            "strategy": self.strategy,
            "max_rounds": self.max_rounds,
            "strategies": list(self.strategies),
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "semantic_provider": self.semantic_provider,
            "semantic_model": self.semantic_model,
            "semantic_fast_provider": self.semantic_fast_provider,
            "semantic_fast_model": self.semantic_fast_model,
            "semantic_strong_provider": self.semantic_strong_provider,
            "semantic_strong_model": self.semantic_strong_model,
            "semantic_cascade_enabled": self.semantic_cascade_enabled,
            "semantic_low_threshold": self.semantic_low_threshold,
            "semantic_high_threshold": self.semantic_high_threshold,
            "request_timeout_seconds": self.request_timeout_seconds,
            "max_retries": self.max_retries,
            "max_tokens": self.max_tokens,
            "semantic_max_tokens": self.semantic_max_tokens,
            "temperature": self.temperature,
            "thinking": self.thinking,
            "reasoning_effort": self.reasoning_effort,
            "experiment_name": self.experiment_name,
            "use_expected_objective_in_repair": self.use_expected_objective_in_repair,
            "mask_expected_objective": self.mask_expected_objective,
            "advisory_mode": self.advisory_mode,
            "static_checks_enabled": self.static_checks_enabled,
            "include_static_checks_in_advisor_prompt": self.include_static_checks_in_advisor_prompt,
            "semantic_prompt_style": self.semantic_prompt_style,
            "include_static_checks_in_repair_prompt": self.include_static_checks_in_repair_prompt,
            "include_semantic_diagnosis_in_repair_prompt": self.include_semantic_diagnosis_in_repair_prompt,
            "include_execution_feedback_in_repair_prompt": self.include_execution_feedback_in_repair_prompt,
            "convergence_logging_enabled": self.convergence_logging_enabled,
            "use_formulation_spec": self.use_formulation_spec,
            "spec_provider": self.spec_provider,
            "spec_model": self.spec_model,
            "spec_max_tokens": self.spec_max_tokens,
            "spec_prompt_style": self.spec_prompt_style,
            "include_formulation_spec_in_codegen": self.include_formulation_spec_in_codegen,
            "include_formulation_spec_in_repair": self.include_formulation_spec_in_repair,
            "use_code_to_spec": self.use_code_to_spec,
            "code_spec_provider": self.code_spec_provider,
            "code_spec_model": self.code_spec_model,
            "code_spec_max_tokens": self.code_spec_max_tokens,
            "code_spec_prompt_style": self.code_spec_prompt_style,
            "include_extracted_spec_in_repair": self.include_extracted_spec_in_repair,
            "use_spec_comparison_diagnosis": self.use_spec_comparison_diagnosis,
            "spec_comparison_provider": self.spec_comparison_provider,
            "spec_comparison_model": self.spec_comparison_model,
            "spec_comparison_max_tokens": self.spec_comparison_max_tokens,
            "include_spec_comparison_in_repair": self.include_spec_comparison_in_repair,
            "semantic_diagnosis_sources": list(self.semantic_diagnosis_sources),
            "feedback_uptake_enabled": self.feedback_uptake_enabled,
            "feedback_uptake_mode": self.feedback_uptake_mode,
            "feedback_uptake_provider": self.feedback_uptake_provider,
            "feedback_uptake_model": self.feedback_uptake_model,
            "feedback_uptake_max_tokens": self.feedback_uptake_max_tokens,
            "advisor_models": list(self.advisor_models),
            "advisor_aggregation": self.advisor_aggregation,
            "repair_feedback_max_chars": self.repair_feedback_max_chars,
            "repair_feedback_max_items": self.repair_feedback_max_items,
            "compress_semantic_feedback": self.compress_semantic_feedback,
            "compression_policy": self.compression_policy,
            "adaptive_repair_feedback_max_chars": self.adaptive_repair_feedback_max_chars,
            "adaptive_repair_feedback_max_items": self.adaptive_repair_feedback_max_items,
            "preserve_all_missing_constraint": self.preserve_all_missing_constraint,
            "preserve_all_wrong_objective": self.preserve_all_wrong_objective,
            "preserve_variable_and_constraint_names": self.preserve_variable_and_constraint_names,
            "preserve_one_freeform_instruction": self.preserve_one_freeform_instruction,
            "preserve_error_type_conditioned_feedback": self.preserve_error_type_conditioned_feedback,
            "semantic_feedback_priority_order": list(self.semantic_feedback_priority_order),
            "output_dir": str(self.output_dir),
        }
        if self.semantic_threshold is not None:
            payload["semantic_threshold"] = self.semantic_threshold
        if self.solver_timeout_seconds is not None:
            payload["solver_timeout_seconds"] = self.solver_timeout_seconds
        return payload

    def with_overrides(
        self,
        *,
        problem_limit: int | None = None,
        strategy: str | None = None,
        dataset_root: str | Path | None = None,
    ) -> "ExperimentConfig":
        changes: dict[str, Any] = {}
        if problem_limit is not None:
            changes["problem_limit"] = problem_limit
        if strategy is not None:
            changes["strategy"] = strategy
            changes["strategies"] = [strategy]
        if dataset_root is not None:
            changes["dataset_root"] = resolve_repo_path(dataset_root)
        return replace(self, **changes)


def load_config(path: str | Path) -> ExperimentConfig:
    config_path = resolve_repo_path(path)
    data = _load_yaml_mapping(config_path)
    required = {
        "problem_source",
        "dataset_name",
        "problem_limit",
        "llm_provider",
        "llm_model",
        "request_timeout_seconds",
        "max_retries",
        "max_tokens",
        "output_dir",
    }
    missing = sorted(required - set(data))
    if missing:
        raise ValueError(f"Missing required config keys: {', '.join(missing)}")

    strategy = str(data.get("strategy") or "")
    raw_strategies = data.get("strategies")
    if raw_strategies is None:
        if not strategy:
            raise ValueError("Config must include 'strategy' or 'strategies'.")
        strategies = [strategy]
    else:
        if not isinstance(raw_strategies, list) or not all(isinstance(item, str) for item in raw_strategies):
            raise ValueError("Config key 'strategies' must be a list of strings.")
        strategies = list(raw_strategies)
        if not strategy:
            strategy = strategies[0]

    raw = dict(data)
    raw.setdefault("_config_path", str(config_path))
    raw.setdefault("_config_stem", config_path.stem)

    return ExperimentConfig(
        problem_source=str(data["problem_source"]),
        dataset_name=str(data["dataset_name"]),
        problem_limit=int(data["problem_limit"]),
        problem_offset=int(data.get("problem_offset", 0)),
        problem_ids=_optional_string_list(data.get("problem_ids")),
        max_problems_per_band=int(data["max_problems_per_band"])
        if data.get("max_problems_per_band") is not None
        else None,
        random_seed=int(data["random_seed"]) if data.get("random_seed") is not None else None,
        strategy=strategy,
        llm_provider=str(data["llm_provider"]),
        llm_model=str(data["llm_model"]),
        semantic_provider=str(data["semantic_provider"]) if data.get("semantic_provider") is not None else None,
        semantic_model=str(data["semantic_model"]) if data.get("semantic_model") is not None else None,
        request_timeout_seconds=int(data["request_timeout_seconds"]),
        max_retries=int(data["max_retries"]),
        max_tokens=int(data["max_tokens"]),
        semantic_max_tokens=int(data["semantic_max_tokens"])
        if data.get("semantic_max_tokens") is not None
        else None,
        temperature=float(data["temperature"]) if data.get("temperature") is not None else None,
        thinking=str(data.get("thinking", "default")),
        reasoning_effort=str(data["reasoning_effort"]) if data.get("reasoning_effort") is not None else None,
        output_dir=resolve_repo_path(data["output_dir"]),
        dataset_root=resolve_repo_path(data["dataset_root"])
        if data.get("dataset_root") is not None
        else None,
        experiment_name=str(data.get("experiment_name") or config_path.stem),
        max_rounds=int(data.get("max_rounds", 1)),
        strategies=strategies,
        semantic_threshold=float(data["semantic_threshold"]) if data.get("semantic_threshold") is not None else None,
        semantic_fast_provider=str(data["semantic_fast_provider"])
        if data.get("semantic_fast_provider") is not None
        else None,
        semantic_fast_model=str(data["semantic_fast_model"])
        if data.get("semantic_fast_model") is not None
        else None,
        semantic_strong_provider=str(data["semantic_strong_provider"])
        if data.get("semantic_strong_provider") is not None
        else None,
        semantic_strong_model=str(data["semantic_strong_model"])
        if data.get("semantic_strong_model") is not None
        else None,
        semantic_cascade_enabled=bool(data.get("semantic_cascade_enabled", False)),
        semantic_low_threshold=float(data.get("semantic_low_threshold", 0.4)),
        semantic_high_threshold=float(data.get("semantic_high_threshold", 0.75)),
        solver_timeout_seconds=int(data["solver_timeout_seconds"])
        if data.get("solver_timeout_seconds") is not None
        else None,
        use_expected_objective_in_repair=bool(data.get("use_expected_objective_in_repair", True)),
        mask_expected_objective=bool(data.get("mask_expected_objective", False)),
        advisory_mode=str(data["advisory_mode"]) if data.get("advisory_mode") is not None else None,
        static_checks_enabled=bool(data.get("static_checks_enabled", True)),
        include_static_checks_in_advisor_prompt=bool(
            data.get("include_static_checks_in_advisor_prompt", True)
        ),
        semantic_prompt_style=str(data.get("semantic_prompt_style", "default")),
        include_static_checks_in_repair_prompt=_optional_bool(
            data.get("include_static_checks_in_repair_prompt")
        ),
        include_semantic_diagnosis_in_repair_prompt=_optional_bool(
            data.get("include_semantic_diagnosis_in_repair_prompt")
        ),
        include_execution_feedback_in_repair_prompt=bool(
            data.get("include_execution_feedback_in_repair_prompt", True)
        ),
        convergence_logging_enabled=bool(data.get("convergence_logging_enabled", True)),
        use_formulation_spec=bool(data.get("use_formulation_spec", False)),
        spec_provider=str(data["spec_provider"]) if data.get("spec_provider") is not None else None,
        spec_model=str(data["spec_model"]) if data.get("spec_model") is not None else None,
        spec_max_tokens=int(data["spec_max_tokens"]) if data.get("spec_max_tokens") is not None else None,
        spec_prompt_style=str(data.get("spec_prompt_style", "full")),
        include_formulation_spec_in_codegen=bool(data.get("include_formulation_spec_in_codegen", False)),
        include_formulation_spec_in_repair=bool(data.get("include_formulation_spec_in_repair", False)),
        use_code_to_spec=bool(data.get("use_code_to_spec", False)),
        code_spec_provider=str(data["code_spec_provider"]) if data.get("code_spec_provider") is not None else None,
        code_spec_model=str(data["code_spec_model"]) if data.get("code_spec_model") is not None else None,
        code_spec_max_tokens=int(data["code_spec_max_tokens"]) if data.get("code_spec_max_tokens") is not None else None,
        code_spec_prompt_style=str(data.get("code_spec_prompt_style", "full")),
        include_extracted_spec_in_repair=bool(data.get("include_extracted_spec_in_repair", False)),
        use_spec_comparison_diagnosis=bool(data.get("use_spec_comparison_diagnosis", False)),
        spec_comparison_provider=str(data["spec_comparison_provider"])
        if data.get("spec_comparison_provider") is not None
        else None,
        spec_comparison_model=str(data["spec_comparison_model"])
        if data.get("spec_comparison_model") is not None
        else None,
        spec_comparison_max_tokens=int(data["spec_comparison_max_tokens"])
        if data.get("spec_comparison_max_tokens") is not None
        else None,
        include_spec_comparison_in_repair=bool(data.get("include_spec_comparison_in_repair", False)),
        semantic_diagnosis_sources=_optional_string_list(data.get("semantic_diagnosis_sources"))
        or ["direct_code"],
        feedback_uptake_enabled=bool(data.get("feedback_uptake_enabled", False)),
        feedback_uptake_mode=str(data.get("feedback_uptake_mode", "off")),
        feedback_uptake_provider=str(data["feedback_uptake_provider"])
        if data.get("feedback_uptake_provider") is not None
        else None,
        feedback_uptake_model=str(data["feedback_uptake_model"])
        if data.get("feedback_uptake_model") is not None
        else None,
        feedback_uptake_max_tokens=int(data["feedback_uptake_max_tokens"])
        if data.get("feedback_uptake_max_tokens") is not None
        else None,
        advisor_models=_optional_dict_list(data.get("advisor_models")) or [],
        advisor_aggregation=str(data.get("advisor_aggregation", "single")),
        repair_feedback_max_chars=int(data["repair_feedback_max_chars"])
        if data.get("repair_feedback_max_chars") is not None
        else None,
        repair_feedback_max_items=int(data["repair_feedback_max_items"])
        if data.get("repair_feedback_max_items") is not None
        else None,
        compress_semantic_feedback=bool(data.get("compress_semantic_feedback", False)),
        compression_policy=str(data.get("compression_policy", "fixed")),
        adaptive_repair_feedback_max_chars=int(data["adaptive_repair_feedback_max_chars"])
        if data.get("adaptive_repair_feedback_max_chars") is not None
        else None,
        adaptive_repair_feedback_max_items=int(data["adaptive_repair_feedback_max_items"])
        if data.get("adaptive_repair_feedback_max_items") is not None
        else None,
        preserve_all_missing_constraint=bool(data.get("preserve_all_missing_constraint", False)),
        preserve_all_wrong_objective=bool(data.get("preserve_all_wrong_objective", False)),
        preserve_variable_and_constraint_names=bool(data.get("preserve_variable_and_constraint_names", False)),
        preserve_one_freeform_instruction=bool(data.get("preserve_one_freeform_instruction", False)),
        preserve_error_type_conditioned_feedback=bool(data.get("preserve_error_type_conditioned_feedback", False)),
        semantic_feedback_priority_order=_optional_string_list(data.get("semantic_feedback_priority_order"))
        or [
            "missing_constraint",
            "wrong_objective",
            "domain_issue",
            "output_issue",
            "api_issue",
            "runtime_risk",
            "other",
        ],
        raw=raw,
    )


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        return _load_simple_yaml(text)

    payload = yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML mapping in {path}.")
    return payload


def _load_simple_yaml(text: str) -> dict[str, Any]:
    """Small fallback parser for the flat pilot YAML used by this harness."""

    data: dict[str, Any] = {}
    current_list_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            if current_list_key is None:
                raise ValueError("YAML list item found before a list key.")
            data[current_list_key].append(_parse_scalar(stripped[2:].strip()))
            continue
        if ":" not in stripped:
            raise ValueError(f"Unsupported YAML line: {raw_line}")
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            data[key] = []
            current_list_key = key
        else:
            data[key] = _parse_scalar(value)
            current_list_key = None
    return data


def _parse_scalar(value: str) -> str | int | float | bool | None:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value.strip("\"'")


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _optional_string_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, (str, int)) for item in value):
        raise ValueError("Config key 'problem_ids' must be a list of strings.")
    return [str(item) for item in value]


def _optional_dict_list(value: Any) -> list[dict[str, Any]] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("Config key 'advisor_models' must be a list of mappings.")
    return [dict(item) for item in value]
