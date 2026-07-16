from __future__ import annotations

import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from src.metrics import aggregate_metrics
from src.result_schema import ProblemResult, RoundResult


def test_metrics_pass_rate_and_average_calls_work() -> None:
    rounds = [
        RoundResult(
            strategy="execution_only",
            problem_id="p1",
            round_index=0,
            valid=True,
            objective=10.0,
            llm_calls=2,
            semantic_calls=0,
            solver_calls=1,
            wall_time_seconds=4.0,
        ),
        RoundResult(
            strategy="execution_only",
            problem_id="p2",
            round_index=0,
            valid=False,
            llm_calls=1,
            semantic_calls=1,
            solver_calls=1,
            wall_time_seconds=2.0,
        ),
    ]

    metrics = aggregate_metrics(rounds)

    assert metrics["pass_rate"] == 0.5
    assert metrics["avg_llm_calls"] == 1.5
    assert metrics["avg_semantic_calls"] == 0.5
    assert metrics["avg_solver_calls"] == 1.0
    assert metrics["invalid_solver_call_ratio"] == 0.5
    assert metrics["avg_final_objective"] == 10.0


def test_metrics_handle_non_executed_records_with_unknown_validity() -> None:
    rounds = [
        RoundResult(
            strategy="vanilla",
            problem_id="p1",
            round_index=0,
            valid=None,
            llm_calls=1,
            solver_calls=0,
            wall_time_seconds=3.0,
            static_check_passed=True,
            code_extracted=True,
            static_issues=["missing_has_optimize_hint"],
            static_signals={"python_compile_ok": True},
            response_char_count=100,
            code_char_count=80,
            code_extraction_warning=None,
            code_changed_from_previous=None,
            response_changed_from_previous=None,
        ),
        RoundResult(
            strategy="vanilla",
            problem_id="p2",
            round_index=0,
            valid=None,
            llm_calls=1,
            solver_calls=0,
            wall_time_seconds=5.0,
            static_check_passed=False,
            code_extracted=False,
            static_issues=["python_compile_failed", "missing_has_model_creation"],
            static_signals={"python_compile_ok": False},
            response_char_count=50,
            code_char_count=25,
            code_extraction_warning="unterminated_python_fence",
            code_changed_from_previous=False,
            response_changed_from_previous=False,
        ),
    ]

    metrics = aggregate_metrics(rounds)

    assert metrics["num_problems"] == 2
    assert metrics["num_llm_calls"] == 2
    assert metrics["avg_wall_time"] == 4.0
    assert metrics["pass_rate"] is None
    assert metrics["static_check_pass_rate"] == 0.5
    assert metrics["code_extraction_rate"] == 0.5
    assert metrics["compile_pass_rate"] == 0.5
    assert metrics["avg_static_issues"] == 1.5
    assert metrics["avg_response_char_count"] == 75.0
    assert metrics["avg_code_char_count"] == 52.5
    assert metrics["unterminated_fence_count"] == 1
    assert metrics["repeated_code_count"] == 1
    assert metrics["repeated_response_count"] == 1
    assert metrics["code_change_rate"] == 0.0


def test_metrics_handle_static_skipped_execution_records() -> None:
    rounds = [
        RoundResult(
            strategy="static_execution",
            problem_id="p1",
            round_index=0,
            valid=False,
            error_type="static_check_failed",
            code_extracted=True,
            static_check_passed=False,
            executed=False,
            execution_success=False,
            expected_objective=7.0,
            objective_match=False,
        ),
        RoundResult(
            strategy="static_execution",
            problem_id="p2",
            round_index=0,
            valid=True,
            error_type=None,
            code_extracted=True,
            static_check_passed=True,
            executed=True,
            execution_success=True,
            parsed_objective=7.0,
            expected_objective=7.0,
            objective_gap=0.0,
            objective_match=True,
        ),
    ]

    metrics = aggregate_metrics(rounds)

    assert metrics["execution_attempt_rate"] == 0.5
    assert metrics["execution_success_rate"] == 1.0
    assert metrics["objective_match_rate"] == 0.5
    assert metrics["static_skipped_count"] == 1
    assert metrics["avg_objective_gap"] == 0.0


def test_metrics_compute_repair_success_and_time_to_first_valid() -> None:
    problem = ProblemResult(
        strategy="execution_only",
        problem_id="p1",
        final_valid=True,
        final_objective=7.0,
        objective_gap=0.0,
        time_to_first_valid=3.0,
        rounds=[
            RoundResult(
                strategy="execution_only",
                problem_id="p1",
                round_index=0,
                valid=False,
                error_type="objective_mismatch",
                llm_calls=1,
                solver_calls=1,
                wall_time_seconds=1.0,
                executed=True,
                execution_success=True,
                parsed_objective=1.0,
                expected_objective=7.0,
                objective_gap=6.0,
                objective_match=False,
                code_changed_from_previous=None,
            ),
            RoundResult(
                strategy="execution_only",
                problem_id="p1",
                round_index=1,
                valid=True,
                llm_calls=1,
                solver_calls=1,
                wall_time_seconds=2.0,
                executed=True,
                execution_success=True,
                parsed_objective=7.0,
                expected_objective=7.0,
                objective_gap=0.0,
                objective_match=True,
                code_changed_from_previous=True,
            ),
        ],
    )

    metrics = aggregate_metrics([problem])

    assert metrics["pass_rate"] == 1.0
    assert metrics["avg_rounds"] == 2.0
    assert metrics["avg_llm_calls"] == 2.0
    assert metrics["avg_solver_calls"] == 2.0
    assert metrics["avg_time_to_first_valid"] == 3.0
    assert metrics["repair_success_count"] == 1
    assert metrics["objective_mismatch_count"] == 1
    assert metrics["avg_final_objective_gap"] == 0.0
    assert metrics["code_change_rate"] == 1.0


def test_metrics_compute_error_persistence_and_gap_movement() -> None:
    problem = ProblemResult(
        strategy="execution_only",
        problem_id="p1",
        final_valid=False,
        objective_gap=9.0,
        rounds=[
            RoundResult(
                strategy="execution_only",
                problem_id="p1",
                round_index=0,
                error_type="runtime_error",
                objective_gap=10.0,
            ),
            RoundResult(
                strategy="execution_only",
                problem_id="p1",
                round_index=1,
                error_type="objective_mismatch",
                objective_gap=6.0,
            ),
            RoundResult(
                strategy="execution_only",
                problem_id="p1",
                round_index=2,
                error_type="objective_mismatch",
                objective_gap=9.0,
            ),
        ],
    )

    metrics = aggregate_metrics([problem])

    assert metrics["same_error_type_persistence_count"] == 1
    assert metrics["runtime_error_resolved_next_round"] == 1
    assert metrics["objective_gap_delta_per_round"] == -0.5
    assert metrics["objective_gap_improved_count"] == 1
    assert metrics["objective_gap_worsened_count"] == 1


def test_metrics_compute_semantic_gate_fields() -> None:
    rounds = [
        RoundResult(
            strategy="semantic_execution",
            problem_id="p1",
            round_index=0,
            error_type="rule_semantic_reject",
            semantic_calls=0,
            solver_calls=0,
            semantic_check_passed=False,
            semantic_score=0.2,
            rule_semantic_reject=True,
        ),
        RoundResult(
            strategy="semantic_execution",
            problem_id="p2",
            round_index=0,
            semantic_calls=1,
            fast_semantic_calls=1,
            solver_calls=1,
            semantic_check_passed=True,
            semantic_score=0.8,
            fast_semantic_score=0.8,
            cascade_fast_accept=True,
        ),
        RoundResult(
            strategy="semantic_execution",
            problem_id="p3",
            round_index=0,
            semantic_calls=2,
            fast_semantic_calls=1,
            strong_semantic_calls=1,
            solver_calls=1,
            semantic_check_passed=True,
            semantic_score=0.9,
            fast_semantic_score=0.5,
            strong_semantic_score=0.9,
            cascade_escalated=True,
        ),
    ]

    metrics = aggregate_metrics(rounds)

    assert metrics["semantic_reject_count"] == 0
    assert metrics["rule_semantic_reject_count"] == 1
    assert metrics["semantic_pass_rate"] == 2 / 3
    assert abs(metrics["avg_semantic_score"] - ((0.2 + 0.8 + 0.9) / 3)) < 1e-12
    assert metrics["solver_calls_avoided_by_semantic"] == 1
    assert metrics["semantic_calls"] == 3
    assert metrics["fast_semantic_calls"] == 2
    assert metrics["strong_semantic_calls"] == 1
    assert metrics["cascade_fast_accept_count"] == 1
    assert metrics["cascade_escalation_count"] == 1
    assert metrics["avg_fast_semantic_score"] == 0.65
    assert metrics["avg_strong_semantic_score"] == 0.9
    assert metrics["semantic_cost_proxy"] == 5
    assert metrics["semantic_false_reject_proxy_count"] is None


def test_metrics_compute_semantic_advisory_used_count() -> None:
    rounds = [
        RoundResult(
            strategy="semantic_advisory_execution",
            problem_id="p1",
            round_index=0,
            semantic_calls=1,
            semantic_score=0.2,
            semantic_check_passed=False,
            semantic_advisory_used=True,
            solver_calls=1,
            executed=True,
            objective_match=False,
        ),
        RoundResult(
            strategy="semantic_advisory_execution",
            problem_id="p2",
            round_index=0,
            semantic_calls=0,
            semantic_advisory_used=False,
            error_type="compile_failed",
            solver_calls=0,
            executed=False,
        ),
    ]

    metrics = aggregate_metrics(rounds)

    assert metrics["semantic_advisory_used_count"] == 1
    assert metrics["semantic_calls"] == 1
    assert metrics["avg_semantic_score"] == 0.2
    assert metrics["avg_solver_calls"] == 0.5
