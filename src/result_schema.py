"""Dataclass result schema for feedback efficiency experiments."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from typing import Any


@dataclass(slots=True)
class RoundResult:
    strategy: str
    problem_id: str
    round_index: int
    valid: bool | None = None
    objective: float | None = None
    error_type: str | None = None
    llm_calls: int = 0
    semantic_calls: int = 0
    fast_semantic_calls: int = 0
    strong_semantic_calls: int = 0
    solver_calls: int = 0
    wall_time_seconds: float = 0.0
    llm_time_seconds: float = 0.0
    solver_time_seconds: float = 0.0
    static_check_passed: bool | None = None
    semantic_check_passed: bool | None = None
    semantic_score: float | None = None
    semantic_should_execute: bool | None = None
    semantic_parse_success: bool | None = None
    semantic_empty_response: bool | None = None
    semantic_parse_failure_type: str | None = None
    semantic_feedback: str | None = None
    semantic_reject_reason: str | None = None
    semantic_feedback_path: str | None = None
    semantic_prompt_path: str | None = None
    semantic_advisory_used: bool = False
    advisory_mode: str | None = None
    advisory_diagnosis: dict[str, Any] = field(default_factory=dict)
    diagnosed_error_types: list[str] = field(default_factory=list)
    repair_instruction_count: int = 0
    judge_confidence: float | None = None
    reject_reasons_count: int = 0
    retrospective_gate_would_execute: bool | None = None
    retrospective_gate_would_skip: bool | None = None
    retrospective_false_rejection: bool | None = None
    retrospective_true_rejection: bool | None = None
    execution_status: str | None = None
    static_check_summary: dict[str, Any] = field(default_factory=dict)
    code_change_ratio: float | None = None
    fast_semantic_score: float | None = None
    strong_semantic_score: float | None = None
    rule_semantic_reject: bool = False
    cascade_escalated: bool = False
    cascade_fast_accept: bool = False
    cascade_fast_reject: bool = False
    semantic_gate_stage: str | None = None
    code_extracted: bool | None = None
    code_path: str | None = None
    raw_response_path: str | None = None
    prompt_path: str | None = None
    code_extraction_warning: str | None = None
    code_hash: str | None = None
    response_hash: str | None = None
    previous_code_hash: str | None = None
    previous_response_hash: str | None = None
    code_changed_from_previous: bool | None = None
    response_changed_from_previous: bool | None = None
    feedback_path: str | None = None
    response_char_count: int | None = None
    code_char_count: int | None = None
    max_tokens: int | None = None
    compile_error: str | None = None
    compile_error_line: int | None = None
    compile_error_type: str | None = None
    executed: bool | None = None
    returncode: int | None = None
    execution_success: bool | None = None
    stdout_path: str | None = None
    stderr_path: str | None = None
    parsed_objective: float | None = None
    expected_objective: float | None = None
    objective_gap: float | None = None
    objective_match: bool | None = None
    static_issues: list[str] = field(default_factory=list)
    static_signals: dict[str, Any] = field(default_factory=dict)
    semantic_missing_constraints: list[str] = field(default_factory=list)
    semantic_variable_issues: list[str] = field(default_factory=list)
    semantic_gurobi_api_issues: list[str] = field(default_factory=list)
    semantic_output_issues: list[str] = field(default_factory=list)
    semantic_wrong_objective: bool | None = None
    semantic_issues: list[str] = field(default_factory=list)
    rule_semantic_issues: list[str] = field(default_factory=list)
    intended_spec_parse_success: bool | None = None
    intended_spec_parse_failure_type: str | None = None
    intended_spec_variable_count: int | None = None
    intended_spec_constraint_count: int | None = None
    intended_spec_objective_direction: str | None = None
    intended_spec_path: str | None = None
    extracted_spec_parse_success: bool | None = None
    extracted_spec_parse_failure_type: str | None = None
    extracted_spec_variable_count: int | None = None
    extracted_spec_constraint_count: int | None = None
    extracted_spec_objective_direction: str | None = None
    extracted_spec_path: str | None = None
    spec_comparison_parse_success: bool | None = None
    spec_comparison_parse_failure_type: str | None = None
    spec_comparison_path: str | None = None
    advisor_count: int | None = None
    advisor_names: list[str] = field(default_factory=list)
    should_execute_by_advisor: dict[str, Any] = field(default_factory=dict)
    should_execute_disagreement: bool | None = None
    diagnosed_error_types_by_advisor: dict[str, Any] = field(default_factory=dict)
    unique_error_types_by_advisor: dict[str, Any] = field(default_factory=dict)
    advisor_error_type_overlap: dict[str, Any] = field(default_factory=dict)
    merged_diagnosed_error_types: list[str] = field(default_factory=list)
    feedback_items_total: int = 0
    feedback_items_implemented: int = 0
    feedback_items_resolved: int = 0
    feedback_objective_gap_improved_count: int = 0
    notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoundResult":
        values = _known_values(cls, data)
        notes = values.get("notes")
        if isinstance(notes, str):
            values["notes"] = [notes]
        static_issues = values.get("static_issues")
        if isinstance(static_issues, str):
            values["static_issues"] = [static_issues]
        for list_field in (
            "semantic_missing_constraints",
            "semantic_variable_issues",
            "semantic_gurobi_api_issues",
            "semantic_output_issues",
            "semantic_issues",
            "rule_semantic_issues",
            "diagnosed_error_types",
            "advisor_names",
            "merged_diagnosed_error_types",
        ):
            value = values.get(list_field)
            if isinstance(value, str):
                values[list_field] = [value]
        return cls(**values)


@dataclass(slots=True)
class ProblemResult:
    strategy: str
    problem_id: str
    rounds: list[RoundResult] = field(default_factory=list)
    final_valid: bool | None = None
    final_objective: float | None = None
    objective_gap: float | None = None
    time_to_first_valid: float | None = None
    notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProblemResult":
        values = _known_values(cls, data)
        values["rounds"] = [RoundResult.from_dict(item) for item in data.get("rounds", [])]
        notes = values.get("notes")
        if isinstance(notes, str):
            values["notes"] = [notes]
        return cls(**values)


@dataclass(slots=True)
class ExperimentResult:
    created_at: str
    config: dict[str, Any]
    problems: list[ProblemResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperimentResult":
        values = _known_values(cls, data)
        values["problems"] = [ProblemResult.from_dict(item) for item in data.get("problems", [])]
        notes = values.get("notes")
        if isinstance(notes, str):
            values["notes"] = [notes]
        return cls(**values)


def _known_values(cls: type[Any], data: dict[str, Any]) -> dict[str, Any]:
    names = {field.name for field in fields(cls)}
    return {key: value for key, value in data.items() if key in names}
