from __future__ import annotations

import json
import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from src.semantic_checker import check_semantics, semantic_rule_precheck


class FakeJudgeClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    def chat(self, messages: list[dict]) -> str:
        assert messages[0]["role"] == "system"
        self.calls += 1
        return self.response


class FakeJudgeClientWithMetadata:
    def __init__(self, response: str, finish_reason: str = "stop") -> None:
        self.response = response
        self.finish_reason = finish_reason
        self.calls = 0

    def chat_with_metadata(self, messages: list[dict]) -> dict:
        assert messages[0]["role"] == "system"
        self.calls += 1
        return {
            "text": self.response,
            "provider": "openai",
            "model": "gpt-5-mini",
            "prompt_char_count": 1234,
            "max_tokens": 1024,
            "finish_reason": self.finish_reason,
            "text_extraction_path": "message.content",
            "raw_response_repr": "<fake>",
        }


def test_semantic_checker_parses_valid_json() -> None:
    payload = {
        "score": 0.8,
        "should_execute": True,
        "missing_constraints": [],
        "wrong_objective": False,
        "variable_issues": [],
        "gurobi_api_issues": [],
        "output_issues": [],
        "feedback": "Looks executable.",
    }
    client = FakeJudgeClient(json.dumps(payload))

    result = check_semantics("Minimize cost.", "def solve_model():\n    return 1.0", llm_client=client)

    assert client.calls == 1
    assert result.passed is True
    assert result.score == 0.8
    assert result.should_execute is True
    assert result.feedback == "Looks executable."


def test_semantic_checker_parses_fenced_json() -> None:
    payload = {
        "score": 0.75,
        "should_execute": True,
        "missing_constraints": ["capacity"],
        "wrong_objective": False,
        "variable_issues": [],
        "gurobi_api_issues": [],
        "output_issues": [],
        "feedback": "Fenced but parseable.",
    }
    client = FakeJudgeClient("```json\n" + json.dumps(payload, indent=2) + "\n```")

    result = check_semantics("Minimize cost.", "def solve_model():\n    return 1.0", llm_client=client)

    assert result.status == "ok"
    assert result.passed is True
    assert result.missing_constraints == ["capacity"]
    assert result.feedback == "Fenced but parseable."


def test_semantic_checker_parses_embedded_json_object() -> None:
    payload = {
        "score": 0.9,
        "should_execute": True,
        "missing_constraints": [],
        "wrong_objective": False,
        "variable_issues": [],
        "gurobi_api_issues": [],
        "output_issues": [],
        "feedback": "Embedded but parseable.",
    }
    client = FakeJudgeClient("Here is the JSON:\n" + json.dumps(payload) + "\nDone.")

    result = check_semantics("Minimize cost.", "def solve_model():\n    return 1.0", llm_client=client)

    assert result.status == "ok"
    assert result.passed is True
    assert result.feedback == "Embedded but parseable."


def test_semantic_checker_handles_invalid_json() -> None:
    result = check_semantics(
        "Minimize cost.",
        "def solve_model():\n    return 1.0",
        llm_client=FakeJudgeClient("not json"),
    )

    assert result.passed is False
    assert result.should_execute is True
    assert result.score == 0.0
    assert result.status == "invalid_json"
    assert "Semantic diagnosis unavailable" in result.feedback
    assert result.diagnosed_error_types == ["parse_failed"]
    assert result.parse_success is False
    assert result.parse_failure_type == "invalid_json"


def test_semantic_checker_classifies_empty_response_with_debug_metadata() -> None:
    result = check_semantics(
        "Minimize cost.",
        "def solve_model():\n    return 1.0",
        llm_client=FakeJudgeClientWithMetadata(""),
    )

    assert result.should_execute is True
    assert result.parse_success is False
    assert result.empty_response is True
    assert result.parse_failure_type == "empty_response"
    assert result.diagnosed_error_types == ["empty_response"]
    assert result.debug_metadata["finish_reason"] == "stop"
    assert result.debug_metadata["prompt_char_count"] == 1234


def test_semantic_rule_precheck_detects_missing_objective_and_return() -> None:
    result = semantic_rule_precheck("def solve_model():\n    print('no return')\n")

    assert result.passed is False
    assert "missing_setObjective" in result.issues
    assert "missing_solve_return" in result.issues


def test_semantic_rule_precheck_detects_addconstrs_misuse_and_nonlinear_product() -> None:
    code = """
def solve_model():
    x = model.addVars(2, name="x")
    y = model.addVars(2, name="y")
    model.addConstrs((x[i] <= 1, "bad") for i in range(2))
    model.setObjective(x[0] * y[0])
    return 0
"""

    result = semantic_rule_precheck(code)

    assert result.passed is False
    assert "addConstrs_misuse_pattern" in result.issues
    assert "nonlinear_decision_variable_product" in result.issues
