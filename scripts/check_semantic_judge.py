#!/usr/bin/env python3
"""Judge-only healthcheck for semantic advisory responses."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from src.code_extractor import extract_code
from src.config import ExperimentConfig, load_config
from src.llm_client import LLMClient
from src.orthought_adapter import ORThoughtAdapter
from src.paths import OUTPUT_ROOT, resolve_repo_path
from src.prompt_builder import build_vanilla_prompt
from src.semantic_checker import check_semantics
from src.static_checker import check_code


def main() -> int:
    args = _parse_args()
    config = load_config(args.config) if args.config else None
    problem_ids = _parse_problem_ids(args.problem_ids)
    if not problem_ids:
        raise SystemExit("At least one --problem_ids value is required.")

    provider = (
        args.advisor_provider
        or args.provider
        or _config_value(config, "semantic_provider")
        or _config_value(config, "llm_provider")
    )
    model = args.advisor_model or args.model or _config_value(config, "semantic_model") or _config_value(config, "llm_model")
    if not provider or not model:
        raise SystemExit("Provide --provider/--model or a config with semantic/LLM model settings.")

    output_dir = (
        resolve_repo_path(args.output_dir)
        if args.output_dir
        else OUTPUT_ROOT / "judge_healthcheck" / f"healthcheck_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "judge_healthcheck.jsonl"

    adapter = ORThoughtAdapter(dataset_name=str(_config_value(config, "dataset_name") or args.dataset_name))
    problems = _select_problems(adapter, problem_ids)
    code_path = resolve_repo_path(args.code_path) if args.code_path else None

    records: list[dict[str, Any]] = []
    for problem in problems:
        code, code_source = _load_or_generate_code(problem, config, code_path)
        static_result = check_code(code, str(problem["problem_text"]))
        static_payload = _static_payload(static_result)
        semantic_max_tokens = int(
            args.semantic_max_tokens
            or args.max_tokens
            or _config_value(config, "semantic_max_tokens")
            or _config_value(config, "max_tokens")
            or 1024
        )
        prompt_style = args.prompt_style or str(_config_value(config, "semantic_prompt_style") or "default")
        semantic_result = check_semantics(
            problem_text=str(problem["problem_text"]),
            generated_code=code,
            provider=str(provider),
            model=str(model),
            threshold=float(_config_value(config, "semantic_threshold") or args.threshold),
            request_timeout_seconds=int(_config_value(config, "request_timeout_seconds") or args.timeout),
            max_retries=int(_config_value(config, "max_retries") or 0),
            temperature=_config_value(config, "temperature"),
            max_tokens=semantic_max_tokens,
            thinking=str(_config_value(config, "thinking") or args.thinking),
            reasoning_effort=_config_value(config, "reasoning_effort"),
            static_checks=static_payload,
            prompt_style=prompt_style,
            round_index=args.round_index,
            advisor_name=f"{provider}:{model}",
        )
        record = build_healthcheck_record(
            config=config,
            problem_id=str(problem["problem_id"]),
            advisor_provider=str(provider),
            advisor_model=str(model),
            semantic_max_tokens=semantic_max_tokens,
            prompt_style=prompt_style,
            code_source=code_source,
            code=code,
            semantic_result=semantic_result.to_dict(),
        )
        _append_jsonl(jsonl_path, record)
        _write_problem_artifacts(output_dir, str(problem["problem_id"]), record)
        records.append(record)
        _print_record(record)

    print(f"Wrote judge healthcheck JSONL: {jsonl_path}")
    _print_summary(records)
    return 0


def build_healthcheck_record(
    *,
    config: ExperimentConfig | None,
    problem_id: str,
    advisor_provider: str,
    advisor_model: str,
    semantic_max_tokens: int | None = None,
    prompt_style: str = "default",
    code_source: str,
    code: str,
    semantic_result: dict[str, Any],
) -> dict[str, Any]:
    advisory = semantic_result.get("advisory_diagnosis")
    if not isinstance(advisory, dict):
        advisory = {}
    diagnosed_error_types = list(semantic_result.get("diagnosed_error_types") or [])
    repair_instructions = list(semantic_result.get("repair_instructions") or [])
    debug = semantic_result.get("debug_metadata") if isinstance(semantic_result.get("debug_metadata"), dict) else {}
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "config_name": _healthcheck_config_name(config),
        "problem_id": problem_id,
        "advisor_provider": advisor_provider,
        "advisor_model": advisor_model,
        "prompt_style": prompt_style,
        "prompt_char_count": debug.get("prompt_char_count"),
        "semantic_max_tokens": semantic_max_tokens if semantic_max_tokens is not None else debug.get("max_tokens"),
        "raw_response_repr": debug.get("raw_response_repr"),
        "message_content_chars": debug.get("message_content_chars"),
        "finish_reason": debug.get("finish_reason"),
        "reasoning_tokens": debug.get("reasoning_tokens"),
        "provider_error": debug.get("provider_error"),
        "nonstandard_content_fields": debug.get("nonstandard_content_fields") or [],
        "response_nonstandard_content_fields": debug.get("response_nonstandard_content_fields") or [],
        "code_source": code_source,
        "generated_code_hash": hashlib.sha256(code.encode("utf-8")).hexdigest(),
        "raw_response_text": str(semantic_result.get("raw_response") or ""),
        "normalized_advisory": advisory,
        "parse_success": bool(semantic_result.get("parse_success")),
        "empty_response": bool(semantic_result.get("empty_response")),
        "parse_failure_type": semantic_result.get("parse_failure_type"),
        "diagnosed_error_types": diagnosed_error_types,
        "repair_instruction_count": len(repair_instructions),
        "should_execute": bool(semantic_result.get("should_execute")),
        "confidence": semantic_result.get("confidence"),
        "debug_metadata": semantic_result.get("debug_metadata") or {},
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Optional experiment config path.")
    parser.add_argument("--provider", help="Advisor provider override.")
    parser.add_argument("--model", help="Advisor model override.")
    parser.add_argument("--advisor_provider", "--advisor-provider", dest="advisor_provider", help="Advisor provider override alias.")
    parser.add_argument("--advisor_model", "--advisor-model", dest="advisor_model", help="Advisor model override alias.")
    parser.add_argument("--dataset_name", default="logior", help="Dataset name when --config is omitted.")
    parser.add_argument(
        "--problem_ids",
        nargs="+",
        required=True,
        help="One or more problem IDs, separated by spaces or commas.",
    )
    parser.add_argument("--code_path", help="Optional generated-code artifact to judge.")
    parser.add_argument("--output_dir", help="Output directory for judge_healthcheck.jsonl.")
    parser.add_argument("--max_tokens", type=int, default=None, help="Advisor output token budget override.")
    parser.add_argument(
        "--semantic_max_tokens",
        "--semantic-max-tokens",
        dest="semantic_max_tokens",
        type=int,
        default=None,
        help="Advisor output token budget override alias.",
    )
    parser.add_argument("--prompt_style", "--prompt-style", dest="prompt_style", choices=["default", "compact"], default=None)
    parser.add_argument("--threshold", type=float, default=0.5, help="Semantic pass threshold.")
    parser.add_argument("--timeout", type=int, default=90, help="Request timeout seconds.")
    parser.add_argument("--thinking", default="default", choices=["default", "disabled", "enabled"])
    parser.add_argument("--round_index", type=int, default=0)
    return parser.parse_args()


def _parse_problem_ids(values: list[str]) -> list[str]:
    problem_ids: list[str] = []
    for value in values:
        problem_ids.extend(item.strip() for item in value.split(",") if item.strip())
    return problem_ids


def _select_problems(adapter: ORThoughtAdapter, problem_ids: list[str]) -> list[dict[str, Any]]:
    problems = adapter.load_problems(limit=None)
    by_id = {str(problem["problem_id"]): problem for problem in problems}
    missing = [problem_id for problem_id in problem_ids if problem_id not in by_id]
    if missing:
        raise SystemExit(f"Unknown problem IDs: {', '.join(missing)}")
    return [by_id[problem_id] for problem_id in problem_ids]


def _load_or_generate_code(
    problem: dict[str, Any],
    config: ExperimentConfig | None,
    code_path: Path | None,
) -> tuple[str, str]:
    if code_path is not None:
        return code_path.read_text(encoding="utf-8"), str(code_path)
    if config is None:
        raise SystemExit("--code_path is required when --config is omitted.")

    client = LLMClient(
        provider=config.llm_provider,
        model=config.llm_model,
        request_timeout_seconds=config.request_timeout_seconds,
        max_retries=config.max_retries,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        thinking=config.thinking,
        reasoning_effort=config.reasoning_effort,
    )
    messages = build_vanilla_prompt(
        problem_text=str(problem["problem_text"]),
        dataset_name=str(problem["dataset_name"]),
        problem_id=str(problem["problem_id"]),
    )
    response = client.chat(messages)
    extraction = extract_code(response)
    return str(extraction["code"]), "generated_round0"


def _static_payload(static_result: Any) -> dict[str, Any]:
    return {
        "passed": bool(getattr(static_result, "passed", False)),
        "issues": list(getattr(static_result, "issues", []) or []),
        "signals": dict(getattr(static_result, "signals", {}) or {}),
        "compile_error": getattr(static_result, "compile_error", None),
        "compile_error_line": getattr(static_result, "compile_error_line", None),
        "compile_error_type": getattr(static_result, "compile_error_type", None),
        "checks": list(getattr(static_result, "checks", []) or []),
    }


def _write_problem_artifacts(output_dir: Path, problem_id: str, record: dict[str, Any]) -> None:
    problem_dir = output_dir / problem_id
    problem_dir.mkdir(parents=True, exist_ok=True)
    (problem_dir / "raw_response.txt").write_text(record["raw_response_text"], encoding="utf-8")
    (problem_dir / "normalized_advisory.json").write_text(
        json.dumps(record["normalized_advisory"], indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _print_record(record: dict[str, Any]) -> None:
    debug = record.get("debug_metadata") if isinstance(record.get("debug_metadata"), dict) else {}
    print(
        json.dumps(
            {
                "problem_id": record["problem_id"],
                "advisor_model": record["advisor_model"],
                "parse_success": record["parse_success"],
                "empty_response": record["empty_response"],
                "parse_failure_type": record["parse_failure_type"],
                "diagnosed_error_types": record["diagnosed_error_types"],
                "repair_instruction_count": record["repair_instruction_count"],
                "should_execute": record["should_execute"],
                "confidence": record["confidence"],
                "finish_reason": debug.get("finish_reason"),
                "prompt_char_count": record.get("prompt_char_count"),
                "semantic_max_tokens": record.get("semantic_max_tokens"),
                "message_content_chars": record.get("message_content_chars"),
                "reasoning_tokens": record.get("reasoning_tokens"),
            },
            sort_keys=True,
        )
    )


def _print_summary(records: list[dict[str, Any]]) -> None:
    total = len(records)
    parse_success = sum(1 for row in records if row.get("parse_success") is True)
    empty_count = sum(1 for row in records if row.get("empty_response") is True)
    prompt_lengths = [
        int(row["prompt_char_count"])
        for row in records
        if isinstance(row.get("prompt_char_count"), int)
    ]
    output_lengths = [
        int(row["message_content_chars"])
        for row in records
        if isinstance(row.get("message_content_chars"), int)
    ]
    failure_types = Counter(str(row.get("parse_failure_type") or "none") for row in records)
    diagnosed_types: Counter[str] = Counter()
    for row in records:
        diagnosed_types.update(str(item) for item in row.get("diagnosed_error_types") or [])
    summary = {
        "total_checks": total,
        "parse_success_rate": parse_success / total if total else 0.0,
        "empty_response_count": empty_count,
        "top_parse_failure_types": dict(failure_types.most_common(5)),
        "top_diagnosed_error_types": dict(diagnosed_types.most_common(5)),
        "average_prompt_char_count": sum(prompt_lengths) / len(prompt_lengths) if prompt_lengths else None,
        "average_message_content_chars": sum(output_lengths) / len(output_lengths) if output_lengths else None,
    }
    print("Aggregate summary:")
    print(json.dumps(summary, sort_keys=True))


def _healthcheck_config_name(config: ExperimentConfig | None) -> str | None:
    if config is None:
        return None
    if config.experiment_name:
        return config.experiment_name
    return str(config.raw.get("_config_stem") or config.strategy)


def _config_value(config: ExperimentConfig | None, name: str) -> Any:
    return getattr(config, name) if config is not None else None


if __name__ == "__main__":
    raise SystemExit(main())
