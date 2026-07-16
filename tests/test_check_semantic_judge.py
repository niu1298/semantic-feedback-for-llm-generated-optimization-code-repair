from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))


def _load_healthcheck_module():
    path = EXPERIMENT_ROOT / "scripts" / "check_semantic_judge.py"
    spec = importlib.util.spec_from_file_location("check_semantic_judge", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_healthcheck_record_schema() -> None:
    module = _load_healthcheck_module()
    semantic_result = {
        "raw_response": "",
        "advisory_diagnosis": {
            "status": "empty_response",
            "parse_success": False,
            "empty_response": True,
        },
        "parse_success": False,
        "empty_response": True,
        "parse_failure_type": "empty_response",
        "diagnosed_error_types": ["empty_response"],
        "repair_instructions": ["Semantic diagnosis unavailable; use execution feedback."],
        "should_execute": True,
        "confidence": 0.0,
        "debug_metadata": {"finish_reason": "stop", "prompt_char_count": 1200},
    }

    record = module.build_healthcheck_record(
        config=None,
        problem_id="prob_037",
        advisor_provider="openai",
        advisor_model="gpt-5-mini",
        semantic_max_tokens=1024,
        prompt_style="compact",
        code_source="artifact.py",
        code="def solve_model():\n    return 1.0",
        semantic_result=semantic_result,
    )

    expected_keys = {
        "timestamp_utc",
        "config_name",
        "problem_id",
        "advisor_provider",
        "advisor_model",
        "prompt_style",
        "prompt_char_count",
        "semantic_max_tokens",
        "raw_response_repr",
        "message_content_chars",
        "finish_reason",
        "reasoning_tokens",
        "provider_error",
        "nonstandard_content_fields",
        "code_source",
        "generated_code_hash",
        "raw_response_text",
        "normalized_advisory",
        "parse_success",
        "empty_response",
        "parse_failure_type",
        "diagnosed_error_types",
        "repair_instruction_count",
        "should_execute",
        "confidence",
        "debug_metadata",
    }
    assert expected_keys <= set(record)
    assert record["problem_id"] == "prob_037"
    assert record["parse_success"] is False
    assert record["empty_response"] is True
    assert record["should_execute"] is True
    assert record["semantic_max_tokens"] == 1024
    assert record["prompt_char_count"] == 1200
