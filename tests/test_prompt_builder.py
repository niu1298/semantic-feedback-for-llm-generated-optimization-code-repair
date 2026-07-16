from __future__ import annotations

import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from src.prompt_builder import build_repair_prompt, build_semantic_judge_prompt, build_vanilla_prompt


def test_prompt_builder_does_not_crash() -> None:
    messages = build_vanilla_prompt("Maximize profit subject to capacity.", "logior", "prob_001")

    assert [message["role"] for message in messages] == ["system", "user"]
    assert "Return only executable Python code" in messages[0]["content"]
    assert "Maximize profit" in messages[1]["content"]
    assert "gurobipy" in messages[1]["content"]
    assert "Return exactly one Python code block" in messages[1]["content"]


def test_repair_prompt_includes_expected_and_parsed_objective() -> None:
    messages = build_repair_prompt(
        problem_text="Minimize cost.",
        previous_code="def solve_model():\n    return 1.0",
        feedback={
            "error_type": "objective_mismatch",
            "static_issues": ["missing_has_optimize_hint"],
            "stdout": "OBJECTIVE=1.0",
            "stderr": "",
            "parsed_objective": 1.0,
            "expected_objective": 7.0,
            "objective_gap": 6.0,
        },
    )

    assert "expected_objective: 7.0" in messages[1]["content"]
    assert "parsed_objective: 1.0" in messages[1]["content"]
    assert "objective_mismatch" in messages[1]["content"]
    assert "wrong objective" in messages[1]["content"]
    assert "decision variables" in messages[1]["content"]
    assert "objective direction and expression" in messages[1]["content"]
    assert "every constraint" in messages[1]["content"]


def test_repair_prompt_omits_masked_expected_objective() -> None:
    messages = build_repair_prompt(
        problem_text="Minimize cost.",
        previous_code="def solve_model():\n    return 1.0",
        feedback={
            "error_type": "objective_mismatch",
            "static_issues": [],
            "stdout": "OBJECTIVE=1.0",
            "stderr": "",
            "parsed_objective": 1.0,
            "expected_objective": None,
            "objective_gap": None,
        },
    )

    content = messages[1]["content"]
    assert "parsed_objective: 1.0" in content
    assert "expected_objective:" not in content
    assert "objective_gap:" not in content


def test_repair_prompt_compile_failed_includes_compile_error() -> None:
    messages = build_repair_prompt(
        problem_text="Minimize cost.",
        previous_code="def solve_model(:\n    return 1.0",
        feedback={
            "error_type": "compile_failed",
            "compile_error": "SyntaxError: invalid syntax",
            "compile_error_type": "SyntaxError",
            "compile_error_line": 1,
            "static_issues": ["python_compile_failed"],
        },
    )

    content = messages[1]["content"]
    assert "did not compile" in content
    assert "SyntaxError: invalid syntax" in content
    assert "compile_error_line: 1" in content


def test_repair_feedback_addconstrs_runtime_hint() -> None:
    messages = build_repair_prompt(
        problem_text="Minimize cost.",
        previous_code="def solve_model():\n    return None",
        feedback={
            "error_type": "runtime_error",
            "stderr": "AttributeError: 'tuple' object has no attribute 'gi_frame'\nModel.addConstrs",
            "static_issues": [],
        },
    )

    content = messages[1]["content"]
    assert "For a single constraint, use model.addConstr" in content
    assert "Never pass (constraint_expr, 'name') into addConstrs" in content


def test_semantic_judge_prompt_requires_strict_json_schema() -> None:
    messages = build_semantic_judge_prompt(
        problem_text="Assign jobs to machines.",
        generated_code="def solve_model():\n    return 0.0",
    )

    content = messages[1]["content"]
    system_content = messages[0]["content"]
    assert "strict JSON only" in system_content
    assert "Diagnose formulation errors separately from execution gating" in system_content
    assert "Do not include chain-of-thought" in system_content
    assert "compact JSON object" in content
    assert "diagnosed_errors" in content
    assert "missing_constraint" in content
    assert "wrong_objective" in content
    assert "api_issue" in content
    assert "Does it likely misuse addConstrs/addConstr" in content


def test_compact_semantic_judge_prompt_keeps_only_failed_static_checks() -> None:
    default_messages = build_semantic_judge_prompt(
        problem_text="Assign jobs to machines.",
        generated_code="def solve_model():\n    return 0.0",
        static_checks={
            "checks": [
                {"check_name": "python_parseable_with_ast", "passed": True, "message": "ok"},
                {
                    "check_name": "calls_set_objective",
                    "passed": False,
                    "severity": "warning",
                    "message": "No setObjective call.",
                    "suggested_fix": "Call model.setObjective.",
                },
            ]
        },
    )
    compact_messages = build_semantic_judge_prompt(
        problem_text="Assign jobs to machines.",
        generated_code="def solve_model():\n    return 0.0",
        static_checks={
            "checks": [
                {"check_name": "python_parseable_with_ast", "passed": True, "message": "ok"},
                {
                    "check_name": "calls_set_objective",
                    "passed": False,
                    "severity": "warning",
                    "message": "No setObjective call.",
                    "suggested_fix": "Call model.setObjective.",
                },
            ]
        },
        prompt_style="compact",
    )

    default_content = default_messages[1]["content"]
    compact_content = compact_messages[1]["content"]
    assert len(compact_content) < len(default_content)
    assert "calls_set_objective" in compact_content
    assert "python_parseable_with_ast" not in compact_content
    assert "No markdown" in compact_messages[0]["content"]
