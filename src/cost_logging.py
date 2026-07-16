"""Token and cost logging helpers for final rerun experiments."""

from __future__ import annotations

import contextlib
import contextvars
import csv
import json
import os
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


COST_USAGE_FIELDS = [
    "timestamp_utc",
    "run_root",
    "run_id",
    "config_name",
    "provider",
    "model",
    "strategy",
    "stage",
    "problem_id",
    "round_index",
    "call_index",
    "success",
    "usage_missing",
    "prompt_tokens",
    "completion_tokens",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cached_tokens",
    "reasoning_tokens",
    "estimated_input_cost_usd",
    "estimated_output_cost_usd",
    "estimated_total_cost_usd",
    "response_id",
    "error_type",
    "notes",
]

COST_SUMMARY_FIELDS = [
    "provider",
    "model",
    "strategy",
    "run_id",
    "stage",
    "api_call_count",
    "calls_with_usage",
    "calls_missing_usage",
    "total_prompt_tokens",
    "total_completion_tokens",
    "total_input_tokens",
    "total_output_tokens",
    "total_tokens",
    "estimated_input_cost_usd",
    "estimated_output_cost_usd",
    "estimated_total_cost_usd",
    "pricing_missing_note",
]

_DEFAULT_PRICING_PATH = Path(__file__).resolve().parents[1] / "configs" / "model_pricing.yaml"
_cost_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "cost_logging_context",
    default={},
)
_call_index = 0


@contextlib.contextmanager
def cost_logging_context(**values: Any) -> Iterator[None]:
    """Temporarily attach run/problem/stage metadata to LLM cost rows."""

    current = dict(_cost_context.get())
    current.update({key: value for key, value in values.items() if value is not None})
    token = _cost_context.set(current)
    try:
        yield
    finally:
        _cost_context.reset(token)


def current_cost_context() -> dict[str, Any]:
    return dict(_cost_context.get())


def next_call_index() -> int:
    global _call_index
    _call_index += 1
    return _call_index


def normalize_usage(usage: Any) -> dict[str, int | None]:
    """Normalize OpenAI chat/completions usage objects and dicts."""

    if usage is None:
        return {
            "prompt_tokens": None,
            "completion_tokens": None,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "cached_tokens": None,
            "reasoning_tokens": None,
        }

    data = _usage_mapping(usage)
    prompt_tokens = _optional_int(_value(data, usage, "prompt_tokens"))
    completion_tokens = _optional_int(_value(data, usage, "completion_tokens"))
    input_tokens = _optional_int(_value(data, usage, "input_tokens"))
    output_tokens = _optional_int(_value(data, usage, "output_tokens"))
    total_tokens = _optional_int(_value(data, usage, "total_tokens"))

    if input_tokens is None:
        input_tokens = prompt_tokens
    if output_tokens is None:
        output_tokens = completion_tokens
    if prompt_tokens is None:
        prompt_tokens = input_tokens
    if completion_tokens is None:
        completion_tokens = output_tokens
    if total_tokens is None:
        total_tokens = _sum_optional(input_tokens, output_tokens)

    prompt_details = _nested(data, usage, "prompt_tokens_details")
    input_details = _nested(data, usage, "input_tokens_details")
    completion_details = _nested(data, usage, "completion_tokens_details")
    output_details = _nested(data, usage, "output_tokens_details")

    cached_tokens = _first_int(
        _value(prompt_details, prompt_details, "cached_tokens"),
        _value(input_details, input_details, "cached_tokens"),
    )
    reasoning_tokens = _first_int(
        _value(completion_details, completion_details, "reasoning_tokens"),
        _value(output_details, output_details, "reasoning_tokens"),
    )

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cached_tokens": cached_tokens,
        "reasoning_tokens": reasoning_tokens,
    }


def append_cost_usage_row(csv_path: str | Path, row: dict[str, Any]) -> None:
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _append_one(path, row)
    _mirror_cost_usage(path, row)


def estimate_cost(
    provider: str,
    model: str,
    tokens: dict[str, int | None],
    pricing_table: dict[str, Any] | None,
) -> dict[str, float | None | str]:
    provider_key = provider.lower()
    model_key = model.lower()
    provider_prices = (pricing_table or {}).get(provider_key)
    if not isinstance(provider_prices, dict):
        return _blank_costs(f"missing pricing provider={provider}")

    model_prices = None
    for candidate, prices in provider_prices.items():
        if str(candidate).lower() == model_key:
            model_prices = prices
            break
    if not isinstance(model_prices, dict):
        return _blank_costs(f"missing pricing model={model}")

    input_price = model_prices.get("input_per_1m_usd")
    output_price = model_prices.get("output_per_1m_usd")
    input_tokens = tokens.get("input_tokens")
    output_tokens = tokens.get("output_tokens")
    if input_price is None or output_price is None:
        return _blank_costs(f"pricing incomplete for {provider}/{model}")

    input_cost = _token_cost(input_tokens, input_price)
    output_cost = _token_cost(output_tokens, output_price)
    total_cost = None if input_cost is None or output_cost is None else input_cost + output_cost
    return {
        "estimated_input_cost_usd": input_cost,
        "estimated_output_cost_usd": output_cost,
        "estimated_total_cost_usd": total_cost,
        "pricing_missing_note": "",
    }


def load_pricing_table(path: str | Path | None = None) -> dict[str, Any]:
    pricing_path = Path(path) if path is not None else _DEFAULT_PRICING_PATH
    if not pricing_path.is_file():
        return {}
    try:
        import yaml  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        return _load_simple_pricing_yaml(pricing_path.read_text(encoding="utf-8"))
    payload = yaml.safe_load(pricing_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def build_cost_usage_row(
    *,
    provider: str,
    model: str,
    usage: Any,
    success: bool,
    response_id: str | None = None,
    error_type: str | None = None,
    notes: str | None = None,
    pricing_table: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = current_cost_context()
    normalized = normalize_usage(usage)
    usage_missing = all(normalized[key] is None for key in ("input_tokens", "output_tokens", "total_tokens"))
    costs = estimate_cost(provider, model, normalized, pricing_table if pricing_table is not None else load_pricing_table())
    row: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "run_root": context.get("run_root") or os.environ.get("FINAL_RERUN_ROOT", ""),
        "run_id": context.get("run_id") or os.environ.get("COST_RUN_ID", ""),
        "config_name": context.get("config_name") or os.environ.get("COST_CONFIG_NAME", ""),
        "provider": provider,
        "model": model,
        "strategy": context.get("strategy", ""),
        "stage": context.get("stage", ""),
        "problem_id": context.get("problem_id", ""),
        "round_index": context.get("round_index", ""),
        "call_index": context.get("call_index") or next_call_index(),
        "success": bool(success),
        "usage_missing": usage_missing,
        "response_id": response_id or "",
        "error_type": error_type or "",
        "notes": notes or costs.get("pricing_missing_note") or "",
    }
    row.update(normalized)
    row.update(
        {
            "estimated_input_cost_usd": costs.get("estimated_input_cost_usd"),
            "estimated_output_cost_usd": costs.get("estimated_output_cost_usd"),
            "estimated_total_cost_usd": costs.get("estimated_total_cost_usd"),
        }
    )
    return row


def summarize_cost_usage(csv_path: str | Path, output_dir: str | Path) -> dict[str, Path | list[dict[str, Any]]]:
    usage_path = Path(csv_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = _read_usage_rows(usage_path)
    summary_rows = _group_cost_rows(rows)
    overall = _overall_row(summary_rows)
    all_rows = summary_rows + ([overall] if overall is not None else [])

    csv_out = out_dir / "cost_summary.csv"
    md_out = out_dir / "cost_summary.md"
    with csv_out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COST_SUMMARY_FIELDS)
        writer.writeheader()
        for row in all_rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in COST_SUMMARY_FIELDS})
    md_out.write_text(_render_cost_summary_md(all_rows), encoding="utf-8")
    return {"csv": csv_out, "md": md_out, "rows": all_rows}


def _usage_mapping(usage: Any) -> dict[str, Any]:
    if isinstance(usage, dict):
        return usage
    if hasattr(usage, "model_dump"):
        dumped = usage.model_dump()
        if isinstance(dumped, dict):
            return dumped
    if hasattr(usage, "to_dict"):
        dumped = usage.to_dict()
        if isinstance(dumped, dict):
            return dumped
    return {}


def _value(mapping: Any, obj: Any, key: str) -> Any:
    if isinstance(mapping, dict) and key in mapping:
        return mapping.get(key)
    return getattr(obj, key, None)


def _nested(mapping: dict[str, Any], obj: Any, key: str) -> Any:
    value = _value(mapping, obj, key)
    return value if value is not None else {}


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_int(*values: Any) -> int | None:
    for value in values:
        parsed = _optional_int(value)
        if parsed is not None:
            return parsed
    return None


def _sum_optional(left: int | None, right: int | None) -> int | None:
    if left is None and right is None:
        return None
    return int(left or 0) + int(right or 0)


def _blank_costs(note: str) -> dict[str, float | None | str]:
    return {
        "estimated_input_cost_usd": None,
        "estimated_output_cost_usd": None,
        "estimated_total_cost_usd": None,
        "pricing_missing_note": note,
    }


def _token_cost(tokens: int | None, price_per_1m: Any) -> float | None:
    if tokens is None:
        return None
    try:
        price = float(price_per_1m)
    except (TypeError, ValueError):
        return None
    return (float(tokens) / 1_000_000.0) * price


def _append_one(path: Path, row: dict[str, Any]) -> None:
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COST_USAGE_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({field: _csv_value(row.get(field)) for field in COST_USAGE_FIELDS})


def _mirror_cost_usage(path: Path, row: dict[str, Any]) -> None:
    run_root = str(row.get("run_root") or "")
    if not run_root:
        return
    mirror = Path(run_root) / "cost_usage.csv"
    try:
        if mirror.resolve() == path.resolve():
            return
    except OSError:
        return
    _append_one(mirror, row)


def _read_usage_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _group_cost_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    notes: dict[tuple[str, str, str, str, str], set[str]] = defaultdict(set)
    for row in rows:
        key = (
            row.get("provider", ""),
            row.get("model", ""),
            row.get("strategy", ""),
            row.get("run_id", ""),
            row.get("stage", ""),
        )
        current = groups.setdefault(
            key,
            {
                "provider": key[0],
                "model": key[1],
                "strategy": key[2],
                "run_id": key[3],
                "stage": key[4],
                "api_call_count": 0,
                "calls_with_usage": 0,
                "calls_missing_usage": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "estimated_input_cost_usd": 0.0,
                "estimated_output_cost_usd": 0.0,
                "estimated_total_cost_usd": 0.0,
                "pricing_missing_note": "",
            },
        )
        current["api_call_count"] += 1
        if _truthy(row.get("usage_missing")):
            current["calls_missing_usage"] += 1
        else:
            current["calls_with_usage"] += 1
        for source, target in (
            ("prompt_tokens", "total_prompt_tokens"),
            ("completion_tokens", "total_completion_tokens"),
            ("input_tokens", "total_input_tokens"),
            ("output_tokens", "total_output_tokens"),
            ("total_tokens", "total_tokens"),
        ):
            current[target] += _int_from_csv(row.get(source))
        for field in (
            "estimated_input_cost_usd",
            "estimated_output_cost_usd",
            "estimated_total_cost_usd",
        ):
            value = row.get(field)
            if value == "":
                notes[key].add("pricing missing or incomplete")
            else:
                current[field] += _float_from_csv(value)
        if row.get("notes"):
            notes[key].add(str(row["notes"]))
    for key, row in groups.items():
        row["pricing_missing_note"] = "; ".join(sorted(notes.get(key, set())))
    return [groups[key] for key in sorted(groups)]


def _overall_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    overall = {
        "provider": "ALL",
        "model": "ALL",
        "strategy": "ALL",
        "run_id": "ALL",
        "stage": "ALL",
        "api_call_count": 0,
        "calls_with_usage": 0,
        "calls_missing_usage": 0,
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_tokens": 0,
        "estimated_input_cost_usd": 0.0,
        "estimated_output_cost_usd": 0.0,
        "estimated_total_cost_usd": 0.0,
        "pricing_missing_note": "",
    }
    notes: set[str] = set()
    for row in rows:
        for field in COST_SUMMARY_FIELDS[5:-1]:
            overall[field] += row.get(field, 0) or 0
        if row.get("pricing_missing_note"):
            notes.add(str(row["pricing_missing_note"]))
    overall["pricing_missing_note"] = "; ".join(sorted(notes))
    return overall


def _render_cost_summary_md(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Cost Summary",
        "",
        "| " + " | ".join(COST_SUMMARY_FIELDS) + " |",
        "| " + " | ".join(["---"] * len(COST_SUMMARY_FIELDS)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_md_value(row.get(field)) for field in COST_SUMMARY_FIELDS) + " |")
    lines.append("")
    return "\n".join(lines)


def _load_simple_pricing_yaml(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    provider: str | None = None
    model: str | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.strip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        key, _, value = raw_line.strip().partition(":")
        if indent == 0:
            provider = key
            data.setdefault(provider, {})
        elif indent == 2 and provider:
            model = key
            data[provider].setdefault(model, {})
        elif indent == 4 and provider and model:
            data[provider][model][key] = None if value.strip() in {"null", ""} else float(value.strip())
    return data


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.12g}"
    return value


def _md_value(value: Any) -> str:
    if value is None or value == "":
        return "n/a"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _truthy(value: Any) -> bool:
    return str(value).lower() in {"true", "1", "yes"}


def _int_from_csv(value: Any) -> int:
    if value in {None, ""}:
        return 0
    try:
        return int(float(str(value)))
    except ValueError:
        return 0


def _float_from_csv(value: Any) -> float:
    if value in {None, ""}:
        return 0.0
    try:
        return float(str(value))
    except ValueError:
        return 0.0


def copy_usage_to_root(csv_path: str | Path, run_root: str | Path) -> Path:
    target = Path(run_root) / "cost_usage.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    if Path(csv_path).resolve() != target.resolve():
        shutil.copy2(csv_path, target)
    return target
