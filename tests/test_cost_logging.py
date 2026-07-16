from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from src.cost_logging import append_cost_usage_row, estimate_cost, normalize_usage


@dataclass
class TokenDetails:
    cached_tokens: int | None = None
    reasoning_tokens: int | None = None


@dataclass
class UsageObject:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt_tokens_details: TokenDetails
    completion_tokens_details: TokenDetails


def test_normalize_usage_object_style() -> None:
    usage = UsageObject(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        prompt_tokens_details=TokenDetails(cached_tokens=3),
        completion_tokens_details=TokenDetails(reasoning_tokens=2),
    )

    normalized = normalize_usage(usage)

    assert normalized["prompt_tokens"] == 10
    assert normalized["completion_tokens"] == 5
    assert normalized["input_tokens"] == 10
    assert normalized["output_tokens"] == 5
    assert normalized["total_tokens"] == 15
    assert normalized["cached_tokens"] == 3
    assert normalized["reasoning_tokens"] == 2


def test_normalize_usage_dict_style() -> None:
    normalized = normalize_usage(
        {
            "input_tokens": 11,
            "output_tokens": 7,
            "total_tokens": 18,
            "input_tokens_details": {"cached_tokens": 4},
            "output_tokens_details": {"reasoning_tokens": 6},
        }
    )

    assert normalized["prompt_tokens"] == 11
    assert normalized["completion_tokens"] == 7
    assert normalized["input_tokens"] == 11
    assert normalized["output_tokens"] == 7
    assert normalized["total_tokens"] == 18
    assert normalized["cached_tokens"] == 4
    assert normalized["reasoning_tokens"] == 6


def test_append_cost_usage_row_creates_csv_header(tmp_path) -> None:
    csv_path = tmp_path / "cost_usage.csv"

    append_cost_usage_row(
        csv_path,
        {
            "timestamp_utc": "2026-05-09T00:00:00+00:00",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "strategy": "execution_only",
            "stage": "generate",
            "success": True,
            "usage_missing": False,
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
        },
    )

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 1
    assert rows[0]["provider"] == "openai"
    assert rows[0]["input_tokens"] == "10"


def test_unknown_pricing_does_not_crash() -> None:
    costs = estimate_cost(
        "openai",
        "unknown-model",
        {"input_tokens": 100, "output_tokens": 50},
        {"openai": {}},
    )

    assert costs["estimated_total_cost_usd"] is None
    assert "missing pricing" in str(costs["pricing_missing_note"])
