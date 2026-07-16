"""Metric aggregation for feedback efficiency experiments."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from .result_schema import ProblemResult, RoundResult

MetricValue = float | int | None

SUMMARY_FIELDS = [
    "num_problems",
    "num_llm_calls",
    "avg_rounds",
    "avg_wall_time",
    "llm_failures",
    "code_extraction_rate",
    "compile_pass_rate",
    "static_check_pass_rate",
    "avg_static_issues",
    "avg_response_char_count",
    "avg_code_char_count",
    "unterminated_fence_count",
    "repeated_code_count",
    "repeated_response_count",
    "code_change_rate",
    "same_error_type_persistence_count",
    "runtime_error_resolved_next_round",
    "objective_gap_delta_per_round",
    "objective_gap_improved_count",
    "objective_gap_worsened_count",
    "execution_attempt_rate",
    "execution_success_rate",
    "objective_match_rate",
    "semantic_reject_count",
    "semantic_pass_rate",
    "avg_semantic_score",
    "semantic_advisory_used_count",
    "solver_calls_avoided_by_semantic",
    "semantic_false_reject_proxy_count",
    "semantic_calls",
    "fast_semantic_calls",
    "strong_semantic_calls",
    "rule_semantic_reject_count",
    "cascade_escalation_count",
    "cascade_fast_accept_count",
    "cascade_fast_reject_count",
    "avg_fast_semantic_score",
    "avg_strong_semantic_score",
    "semantic_cost_proxy",
    "static_skipped_count",
    "runtime_error_count",
    "timeout_count",
    "no_objective_count",
    "repair_success_count",
    "compile_failed_count",
    "objective_mismatch_count",
    "pass_rate",
    "avg_llm_calls",
    "avg_semantic_calls",
    "avg_solver_calls",
    "avg_wall_time_seconds",
    "invalid_solver_call_ratio",
    "avg_final_objective",
    "avg_time_to_first_valid",
    "avg_objective_gap",
    "avg_final_objective_gap",
]


def aggregate_metrics(items: Sequence[ProblemResult] | Sequence[RoundResult]) -> dict[str, MetricValue]:
    if not items:
        return {
            "num_problems": 0,
            "num_llm_calls": 0,
            "avg_rounds": 0.0,
            "avg_wall_time": 0.0,
            "llm_failures": 0,
            "code_extraction_rate": None,
            "compile_pass_rate": None,
            "static_check_pass_rate": None,
            "avg_static_issues": 0.0,
            "avg_response_char_count": None,
            "avg_code_char_count": None,
            "unterminated_fence_count": 0,
            "repeated_code_count": 0,
            "repeated_response_count": 0,
            "code_change_rate": None,
            "same_error_type_persistence_count": 0,
            "runtime_error_resolved_next_round": 0,
            "objective_gap_delta_per_round": None,
            "objective_gap_improved_count": 0,
            "objective_gap_worsened_count": 0,
            "execution_attempt_rate": None,
            "execution_success_rate": None,
            "objective_match_rate": None,
            "semantic_reject_count": 0,
            "semantic_pass_rate": None,
            "avg_semantic_score": None,
            "semantic_advisory_used_count": 0,
            "solver_calls_avoided_by_semantic": 0,
            "semantic_false_reject_proxy_count": None,
            "semantic_calls": 0,
            "fast_semantic_calls": 0,
            "strong_semantic_calls": 0,
            "rule_semantic_reject_count": 0,
            "cascade_escalation_count": 0,
            "cascade_fast_accept_count": 0,
            "cascade_fast_reject_count": 0,
            "avg_fast_semantic_score": None,
            "avg_strong_semantic_score": None,
            "semantic_cost_proxy": 0,
            "static_skipped_count": 0,
            "runtime_error_count": 0,
            "timeout_count": 0,
            "no_objective_count": 0,
            "repair_success_count": 0,
            "compile_failed_count": 0,
            "objective_mismatch_count": 0,
            "pass_rate": 0.0,
            "avg_llm_calls": 0.0,
            "avg_semantic_calls": 0.0,
            "avg_solver_calls": 0.0,
            "avg_wall_time_seconds": 0.0,
            "invalid_solver_call_ratio": 0.0,
            "avg_final_objective": None,
            "avg_time_to_first_valid": None,
            "avg_objective_gap": None,
            "avg_final_objective_gap": None,
        }

    first = items[0]
    if isinstance(first, ProblemResult):
        problems = list(items)  # type: ignore[arg-type]
        rounds = [round_result for problem in problems for round_result in problem.rounds]
        return _aggregate_problem_results(problems, rounds)

    rounds = list(items)  # type: ignore[arg-type]
    return _aggregate_round_results(rounds)


def aggregate_by_strategy(problems: Iterable[ProblemResult]) -> dict[str, dict[str, MetricValue]]:
    grouped: dict[str, list[ProblemResult]] = {}
    for problem in problems:
        grouped.setdefault(problem.strategy, []).append(problem)
    return {strategy: aggregate_metrics(group) for strategy, group in grouped.items()}


def _aggregate_problem_results(
    problems: list[ProblemResult],
    rounds: list[RoundResult],
) -> dict[str, MetricValue]:
    count = len(problems)
    final_objectives = [
        problem.final_objective
        for problem in problems
        if problem.final_valid and problem.final_objective is not None
    ]
    first_valid_times = [
        problem.time_to_first_valid
        for problem in problems
        if problem.time_to_first_valid is not None
    ]
    final_objective_gaps = [
        problem.objective_gap
        for problem in problems
        if problem.objective_gap is not None
    ]
    known_validity = [problem.final_valid for problem in problems if problem.final_valid is not None]
    problem_wall_times = [sum(round.wall_time_seconds for round in problem.rounds) for problem in problems]
    round_pairs = _round_pairs_from_problems(problems)
    return {
        "num_problems": count,
        "num_llm_calls": sum(round.llm_calls for round in rounds),
        "avg_rounds": _mean([len(problem.rounds) for problem in problems]) or 0.0,
        "avg_wall_time": _mean(problem_wall_times) or 0.0,
        "llm_failures": sum(1 for round in rounds if round.error_type == "llm_failed"),
        "code_extraction_rate": _code_extraction_rate(rounds),
        "compile_pass_rate": _compile_pass_rate(rounds),
        "static_check_pass_rate": _static_check_pass_rate(rounds),
        "avg_static_issues": _avg_static_issues(rounds),
        "avg_response_char_count": _mean(_response_char_counts(rounds)),
        "avg_code_char_count": _mean(_code_char_counts(rounds)),
        "unterminated_fence_count": _unterminated_fence_count(rounds),
        "repeated_code_count": _repeated_count(rounds, "code_changed_from_previous"),
        "repeated_response_count": _repeated_count(rounds, "response_changed_from_previous"),
        "code_change_rate": _change_rate(rounds, "code_changed_from_previous"),
        "same_error_type_persistence_count": _same_error_type_persistence_count(round_pairs),
        "runtime_error_resolved_next_round": _runtime_error_resolved_next_round(round_pairs),
        "objective_gap_delta_per_round": _mean(_objective_gap_deltas(round_pairs)),
        "objective_gap_improved_count": _objective_gap_improved_count(round_pairs),
        "objective_gap_worsened_count": _objective_gap_worsened_count(round_pairs),
        "execution_attempt_rate": _execution_attempt_rate(rounds),
        "execution_success_rate": _execution_success_rate(rounds),
        "objective_match_rate": _objective_match_rate(rounds),
        "semantic_reject_count": _error_count(rounds, "semantic_reject"),
        "semantic_pass_rate": _semantic_pass_rate(rounds),
        "avg_semantic_score": _avg_semantic_score(rounds),
        "semantic_advisory_used_count": _semantic_advisory_used_count(rounds),
        "solver_calls_avoided_by_semantic": _solver_calls_avoided_by_semantic(rounds),
        "semantic_false_reject_proxy_count": None,
        "semantic_calls": sum(round.semantic_calls for round in rounds),
        "fast_semantic_calls": sum(round.fast_semantic_calls for round in rounds),
        "strong_semantic_calls": sum(round.strong_semantic_calls for round in rounds),
        "rule_semantic_reject_count": _rule_semantic_reject_count(rounds),
        "cascade_escalation_count": _cascade_count(rounds, "cascade_escalated"),
        "cascade_fast_accept_count": _cascade_count(rounds, "cascade_fast_accept"),
        "cascade_fast_reject_count": _cascade_count(rounds, "cascade_fast_reject"),
        "avg_fast_semantic_score": _mean([round.fast_semantic_score for round in rounds]),
        "avg_strong_semantic_score": _mean([round.strong_semantic_score for round in rounds]),
        "semantic_cost_proxy": _semantic_cost_proxy(rounds),
        "static_skipped_count": _error_count(rounds, "static_check_failed"),
        "runtime_error_count": _error_count(rounds, "runtime_error"),
        "timeout_count": _error_count(rounds, "timeout"),
        "no_objective_count": _error_count(rounds, "no_objective"),
        "repair_success_count": _repair_success_count(problems),
        "compile_failed_count": _error_count(rounds, "compile_failed"),
        "objective_mismatch_count": _error_count(rounds, "objective_mismatch"),
        "pass_rate": _pass_rate(known_validity),
        "avg_llm_calls": _mean([sum(round.llm_calls for round in problem.rounds) for problem in problems]) or 0.0,
        "avg_semantic_calls": _mean([sum(round.semantic_calls for round in problem.rounds) for problem in problems])
        or 0.0,
        "avg_solver_calls": _mean([sum(round.solver_calls for round in problem.rounds) for problem in problems]) or 0.0,
        "avg_wall_time_seconds": _mean(
            [sum(round.wall_time_seconds for round in problem.rounds) for problem in problems]
        )
        or 0.0,
        "invalid_solver_call_ratio": _invalid_solver_call_ratio(rounds),
        "avg_final_objective": _mean(final_objectives),
        "avg_time_to_first_valid": _mean(first_valid_times),
        "avg_objective_gap": _mean(_objective_gaps(rounds)),
        "avg_final_objective_gap": _mean(final_objective_gaps),
    }


def _aggregate_round_results(rounds: list[RoundResult]) -> dict[str, MetricValue]:
    count = len(rounds)
    final_objectives = [round.objective for round in rounds if round.valid and round.objective is not None]
    known_validity = [round.valid for round in rounds if round.valid is not None]
    round_pairs = _round_pairs(rounds)
    return {
        "num_problems": count,
        "num_llm_calls": sum(round.llm_calls for round in rounds),
        "avg_rounds": 1.0 if rounds else 0.0,
        "avg_wall_time": _mean([round.wall_time_seconds for round in rounds]) or 0.0,
        "llm_failures": sum(1 for round in rounds if round.error_type == "llm_failed"),
        "code_extraction_rate": _code_extraction_rate(rounds),
        "compile_pass_rate": _compile_pass_rate(rounds),
        "static_check_pass_rate": _static_check_pass_rate(rounds),
        "avg_static_issues": _avg_static_issues(rounds),
        "avg_response_char_count": _mean(_response_char_counts(rounds)),
        "avg_code_char_count": _mean(_code_char_counts(rounds)),
        "unterminated_fence_count": _unterminated_fence_count(rounds),
        "repeated_code_count": _repeated_count(rounds, "code_changed_from_previous"),
        "repeated_response_count": _repeated_count(rounds, "response_changed_from_previous"),
        "code_change_rate": _change_rate(rounds, "code_changed_from_previous"),
        "same_error_type_persistence_count": _same_error_type_persistence_count(round_pairs),
        "runtime_error_resolved_next_round": _runtime_error_resolved_next_round(round_pairs),
        "objective_gap_delta_per_round": _mean(_objective_gap_deltas(round_pairs)),
        "objective_gap_improved_count": _objective_gap_improved_count(round_pairs),
        "objective_gap_worsened_count": _objective_gap_worsened_count(round_pairs),
        "execution_attempt_rate": _execution_attempt_rate(rounds),
        "execution_success_rate": _execution_success_rate(rounds),
        "objective_match_rate": _objective_match_rate(rounds),
        "semantic_reject_count": _error_count(rounds, "semantic_reject"),
        "semantic_pass_rate": _semantic_pass_rate(rounds),
        "avg_semantic_score": _avg_semantic_score(rounds),
        "semantic_advisory_used_count": _semantic_advisory_used_count(rounds),
        "solver_calls_avoided_by_semantic": _solver_calls_avoided_by_semantic(rounds),
        "semantic_false_reject_proxy_count": None,
        "semantic_calls": sum(round.semantic_calls for round in rounds),
        "fast_semantic_calls": sum(round.fast_semantic_calls for round in rounds),
        "strong_semantic_calls": sum(round.strong_semantic_calls for round in rounds),
        "rule_semantic_reject_count": _rule_semantic_reject_count(rounds),
        "cascade_escalation_count": _cascade_count(rounds, "cascade_escalated"),
        "cascade_fast_accept_count": _cascade_count(rounds, "cascade_fast_accept"),
        "cascade_fast_reject_count": _cascade_count(rounds, "cascade_fast_reject"),
        "avg_fast_semantic_score": _mean([round.fast_semantic_score for round in rounds]),
        "avg_strong_semantic_score": _mean([round.strong_semantic_score for round in rounds]),
        "semantic_cost_proxy": _semantic_cost_proxy(rounds),
        "static_skipped_count": _error_count(rounds, "static_check_failed"),
        "runtime_error_count": _error_count(rounds, "runtime_error"),
        "timeout_count": _error_count(rounds, "timeout"),
        "no_objective_count": _error_count(rounds, "no_objective"),
        "repair_success_count": 0,
        "compile_failed_count": _error_count(rounds, "compile_failed"),
        "objective_mismatch_count": _error_count(rounds, "objective_mismatch"),
        "pass_rate": _pass_rate(known_validity),
        "avg_llm_calls": _mean([round.llm_calls for round in rounds]) or 0.0,
        "avg_semantic_calls": _mean([round.semantic_calls for round in rounds]) or 0.0,
        "avg_solver_calls": _mean([round.solver_calls for round in rounds]) or 0.0,
        "avg_wall_time_seconds": _mean([round.wall_time_seconds for round in rounds]) or 0.0,
        "invalid_solver_call_ratio": _invalid_solver_call_ratio(rounds),
        "avg_final_objective": _mean(final_objectives),
        "avg_time_to_first_valid": _mean([round.wall_time_seconds for round in rounds if round.valid]),
        "avg_objective_gap": _mean(_objective_gaps(rounds)),
        "avg_final_objective_gap": _mean(_objective_gaps(rounds)),
    }


def _invalid_solver_call_ratio(rounds: list[RoundResult]) -> float:
    solver_calls = sum(round.solver_calls for round in rounds)
    if solver_calls == 0:
        return 0.0
    invalid_solver_calls = sum(round.solver_calls for round in rounds if not round.valid)
    return invalid_solver_calls / solver_calls


def _static_check_pass_rate(rounds: list[RoundResult]) -> float | None:
    checked = [round.static_check_passed for round in rounds if round.static_check_passed is not None]
    return _pass_rate(checked)


def _code_extraction_rate(rounds: list[RoundResult]) -> float | None:
    extracted = [round.code_extracted for round in rounds if round.code_extracted is not None]
    return _pass_rate(extracted)


def _compile_pass_rate(rounds: list[RoundResult]) -> float | None:
    values = []
    for round in rounds:
        if "python_compile_ok" in round.static_signals:
            values.append(bool(round.static_signals["python_compile_ok"]))
    return _pass_rate(values)


def _avg_static_issues(rounds: list[RoundResult]) -> float:
    if not rounds:
        return 0.0
    return _mean([len(round.static_issues) for round in rounds]) or 0.0


def _response_char_counts(rounds: list[RoundResult]) -> list[int | None]:
    return [_round_int_value(round, "response_char_count") for round in rounds]


def _code_char_counts(rounds: list[RoundResult]) -> list[int | None]:
    return [_round_int_value(round, "code_char_count") for round in rounds]


def _unterminated_fence_count(rounds: list[RoundResult]) -> int:
    count = 0
    for round in rounds:
        warning = round.code_extraction_warning or round.metadata.get("code_extraction_warning")
        if isinstance(warning, str) and warning.startswith("unterminated"):
            count += 1
    return count


def _repeated_count(rounds: list[RoundResult], field_name: str) -> int:
    return sum(1 for round in rounds if getattr(round, field_name, None) is False)


def _change_rate(rounds: list[RoundResult], field_name: str) -> float | None:
    values = [getattr(round, field_name, None) for round in rounds if getattr(round, field_name, None) is not None]
    return _pass_rate([bool(value) for value in values])


def _round_pairs_from_problems(problems: list[ProblemResult]) -> list[tuple[RoundResult, RoundResult]]:
    pairs: list[tuple[RoundResult, RoundResult]] = []
    for problem in problems:
        pairs.extend(_round_pairs(problem.rounds))
    return pairs


def _round_pairs(rounds: list[RoundResult]) -> list[tuple[RoundResult, RoundResult]]:
    return list(zip(rounds, rounds[1:]))


def _same_error_type_persistence_count(pairs: list[tuple[RoundResult, RoundResult]]) -> int:
    return sum(
        1
        for previous, current in pairs
        if previous.error_type is not None and previous.error_type == current.error_type
    )


def _runtime_error_resolved_next_round(pairs: list[tuple[RoundResult, RoundResult]]) -> int:
    return sum(
        1
        for previous, current in pairs
        if previous.error_type == "runtime_error" and current.error_type != "runtime_error"
    )


def _objective_gap_deltas(pairs: list[tuple[RoundResult, RoundResult]]) -> list[float]:
    deltas: list[float] = []
    for previous, current in pairs:
        if previous.objective_gap is None or current.objective_gap is None:
            continue
        deltas.append(float(current.objective_gap) - float(previous.objective_gap))
    return deltas


def _objective_gap_improved_count(pairs: list[tuple[RoundResult, RoundResult]]) -> int:
    return sum(1 for delta in _objective_gap_deltas(pairs) if delta < 0)


def _objective_gap_worsened_count(pairs: list[tuple[RoundResult, RoundResult]]) -> int:
    return sum(1 for delta in _objective_gap_deltas(pairs) if delta > 0)


def _execution_attempt_rate(rounds: list[RoundResult]) -> float | None:
    values = [round.executed for round in rounds if round.executed is not None]
    return _pass_rate(values)


def _execution_success_rate(rounds: list[RoundResult]) -> float | None:
    attempted = [round for round in rounds if round.executed]
    if not attempted:
        return None
    return _pass_rate([bool(round.execution_success) for round in attempted])


def _objective_match_rate(rounds: list[RoundResult]) -> float | None:
    values = [round.objective_match for round in rounds if round.objective_match is not None]
    return _pass_rate(values)


def _semantic_pass_rate(rounds: list[RoundResult]) -> float | None:
    values = [round.semantic_check_passed for round in rounds if round.semantic_check_passed is not None]
    return _pass_rate(values)


def _avg_semantic_score(rounds: list[RoundResult]) -> float | None:
    return _mean([round.semantic_score for round in rounds if round.semantic_score is not None])


def _semantic_advisory_used_count(rounds: list[RoundResult]) -> int:
    return sum(
        1
        for round in rounds
        if round.semantic_advisory_used
        or (round.strategy == "semantic_advisory_execution" and round.semantic_calls > 0)
    )


def _solver_calls_avoided_by_semantic(rounds: list[RoundResult]) -> int:
    return sum(
        1
        for round in rounds
        if round.error_type in {"semantic_reject", "rule_semantic_reject"} and round.solver_calls == 0
    )


def _rule_semantic_reject_count(rounds: list[RoundResult]) -> int:
    return sum(1 for round in rounds if round.rule_semantic_reject or round.error_type == "rule_semantic_reject")


def _cascade_count(rounds: list[RoundResult], field_name: str) -> int:
    return sum(1 for round in rounds if bool(getattr(round, field_name, False)))


def _semantic_cost_proxy(rounds: list[RoundResult]) -> int:
    return sum(round.fast_semantic_calls for round in rounds) + 3 * sum(
        round.strong_semantic_calls for round in rounds
    )


def _objective_gaps(rounds: list[RoundResult]) -> list[float]:
    return [
        float(round.objective_gap)
        for round in rounds
        if round.executed and round.expected_objective is not None and round.objective_gap is not None
    ]


def _error_count(rounds: list[RoundResult], error_type: str) -> int:
    return sum(1 for round in rounds if round.error_type == error_type)


def _repair_success_count(problems: list[ProblemResult]) -> int:
    return sum(1 for problem in problems if problem.final_valid and len(problem.rounds) > 1)


def _round_int_value(round: RoundResult, name: str) -> int | None:
    value = getattr(round, name, None)
    if value is None:
        value = round.metadata.get(name)
    if value is None:
        return None
    return int(value)


def _pass_rate(values: list[bool]) -> float | None:
    if not values:
        return None
    return sum(1 for value in values if value) / len(values)


def _mean(values: Iterable[float | int | None]) -> float | None:
    concrete = [float(value) for value in values if value is not None]
    if not concrete:
        return None
    return sum(concrete) / len(concrete)
