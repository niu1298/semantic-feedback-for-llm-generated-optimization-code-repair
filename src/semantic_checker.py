"""Lightweight LLM-as-judge semantic checker."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .advisory import diagnosis_to_legacy_fields, parse_advisory_response
from .llm_client import LLMClient
from .prompt_builder import build_semantic_judge_prompt


@dataclass(frozen=True, slots=True)
class SemanticCheckResult:
    passed: bool
    skipped: bool
    status: str
    score: float
    should_execute: bool
    missing_constraints: list[str] = field(default_factory=list)
    wrong_objective: bool = False
    variable_issues: list[str] = field(default_factory=list)
    gurobi_api_issues: list[str] = field(default_factory=list)
    output_issues: list[str] = field(default_factory=list)
    feedback: str = ""
    raw_response: str = ""
    advisory_diagnosis: dict[str, Any] = field(default_factory=dict)
    diagnosed_error_types: list[str] = field(default_factory=list)
    repair_instructions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    reject_reasons: list[str] = field(default_factory=list)
    parse_success: bool | None = None
    empty_response: bool = False
    parse_failure_type: str | None = None
    debug_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RuleSemanticPrecheckResult:
    passed: bool
    issues: list[str] = field(default_factory=list)
    feedback: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def semantic_rule_precheck(generated_code: str) -> RuleSemanticPrecheckResult:
    """Cheap local semantic guard before spending an LLM judge call."""

    issues: list[str] = []
    if _has_addconstrs_misuse_pattern(generated_code):
        issues.append("addConstrs_misuse_pattern")

    try:
        tree = ast.parse(generated_code)
    except SyntaxError:
        return RuleSemanticPrecheckResult(passed=True)

    if not _has_set_objective(tree):
        issues.append("missing_setObjective")
    if not _has_solve_return(tree):
        issues.append("missing_solve_return")
    if _has_obvious_decision_var_product(tree):
        issues.append("nonlinear_decision_variable_product")

    if not issues:
        return RuleSemanticPrecheckResult(passed=True)
    return RuleSemanticPrecheckResult(
        passed=False,
        issues=issues,
        feedback="Rule semantic precheck failed: " + ", ".join(issues),
    )


def check_semantics(
    problem_text: str,
    generated_code: str,
    provider: str = "openai",
    model: str = "gpt-4o-mini",
    threshold: float = 0.6,
    request_timeout_seconds: int = 45,
    max_retries: int = 0,
    temperature: float | None = 0.0,
    max_tokens: int = 1024,
    thinking: str = "default",
    reasoning_effort: str | None = None,
    llm_client: Any | None = None,
    static_checks: dict[str, Any] | list[dict[str, Any]] | None = None,
    prompt_style: str = "default",
    round_index: int = 0,
    advisor_name: str | None = None,
) -> SemanticCheckResult:
    client = llm_client or LLMClient(
        provider=provider,
        model=model,
        request_timeout_seconds=request_timeout_seconds,
        max_retries=max_retries,
        temperature=temperature,
        max_tokens=max_tokens,
        thinking=thinking,
        reasoning_effort=reasoning_effort,
    )
    effective_advisor_name = advisor_name or f"{provider}:{model}"
    messages = build_semantic_judge_prompt(
        problem_text,
        generated_code,
        static_checks=static_checks,
        prompt_style=prompt_style,
    )
    debug_metadata = _semantic_debug_metadata(
        provider=provider,
        model=model,
        messages=messages,
        max_tokens=max_tokens,
    )
    try:
        if hasattr(client, "chat_with_metadata"):
            response_payload = client.chat_with_metadata(messages)
            raw_response = str(response_payload.get("text", ""))
            debug_metadata.update(
                {key: value for key, value in response_payload.items() if key != "text"}
            )
        else:
            raw_response = client.chat(messages)
    except Exception as exc:
        debug_metadata["provider_error"] = f"{exc.__class__.__name__}: {exc}"
        return SemanticCheckResult(
            passed=False,
            skipped=False,
            status="llm_error",
            score=0.0,
            should_execute=False,
            feedback=f"semantic checker LLM failed: {exc.__class__.__name__}: {exc}",
            raw_response="",
            parse_success=False,
            empty_response=False,
            parse_failure_type="llm_error",
            debug_metadata=debug_metadata,
        )
    diagnosis = parse_advisory_response(
        raw_response,
        round_index=round_index,
        advisor_name=effective_advisor_name,
        parse_debug=debug_metadata,
    )
    legacy = diagnosis_to_legacy_fields(diagnosis)
    score = _clamp_score(diagnosis.score)
    should_execute = bool(diagnosis.should_execute)
    passed = score >= threshold and should_execute
    feedback = legacy["feedback"]
    if not diagnosis.parse_success and not feedback:
        feedback = "Semantic diagnosis unavailable; use execution feedback."
    return SemanticCheckResult(
        passed=passed,
        skipped=False,
        status=diagnosis.status,
        score=score,
        should_execute=should_execute,
        missing_constraints=_string_list(legacy.get("missing_constraints")),
        wrong_objective=bool(legacy.get("wrong_objective", False)),
        variable_issues=_string_list(legacy.get("variable_issues")),
        gurobi_api_issues=_string_list(legacy.get("gurobi_api_issues")),
        output_issues=_string_list(legacy.get("output_issues")),
        feedback=feedback,
        raw_response=raw_response,
        advisory_diagnosis=diagnosis.to_dict(),
        diagnosed_error_types=[item.type for item in diagnosis.diagnosed_errors],
        repair_instructions=list(diagnosis.repair_instructions),
        confidence=diagnosis.confidence,
        reject_reasons=list(diagnosis.reject_reasons),
        parse_success=diagnosis.parse_success,
        empty_response=diagnosis.empty_response,
        parse_failure_type=diagnosis.parse_failure_type,
        debug_metadata=diagnosis.parse_debug,
    )


def skipped_semantic_result(reason: str) -> SemanticCheckResult:
    return SemanticCheckResult(
        passed=False,
        skipped=True,
        status=reason,
        score=0.0,
        should_execute=False,
        feedback=reason,
    )


def _clamp_score(value: object) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, score))


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _semantic_debug_metadata(
    *,
    provider: str,
    model: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
) -> dict[str, Any]:
    prompt_chars = 0
    for message in messages:
        prompt_chars += len(str(message.get("content", "")))
    return {
        "advisor_provider": provider,
        "advisor_model": model,
        "prompt_char_count": prompt_chars,
        "max_tokens": max_tokens,
    }


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", flags=re.DOTALL | re.IGNORECASE)


def _load_json_payload(raw_response: str) -> Any:
    try:
        return json.loads(raw_response)
    except json.JSONDecodeError:
        pass

    for match in _FENCED_JSON_RE.finditer(raw_response):
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            continue

    start = raw_response.find("{")
    if start >= 0:
        decoder = json.JSONDecoder()
        payload, _ = decoder.raw_decode(raw_response[start:])
        return payload
    raise json.JSONDecodeError("No JSON object found", raw_response, 0)


def _has_addconstrs_misuse_pattern(code: str) -> bool:
    patterns = (
        r"\.addConstrs\s*\([^)]*,\s*['\"]",
        r"\.addConstrs\s*\(\s*\([^)]*,\s*['\"]",
    )
    return any(re.search(pattern, code, flags=re.DOTALL) for pattern in patterns)


def _has_set_objective(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "setObjective":
                return True
    return False


def _has_solve_return(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {"solve", "solve_model"}:
            return any(
                isinstance(child, ast.Return) and child.value is not None
                for child in ast.walk(node)
            )
    return False


def _has_obvious_decision_var_product(tree: ast.AST) -> bool:
    decision_var_roots = _decision_variable_roots(tree)
    if not decision_var_roots:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Mult):
            continue
        if _references_decision_var(node.left, decision_var_roots) and _references_decision_var(
            node.right,
            decision_var_roots,
        ):
            return True
    return False


def _decision_variable_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Call) or not isinstance(node.value.func, ast.Attribute):
            continue
        if node.value.func.attr not in {"addVar", "addVars"}:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                roots.add(target.id)
    return roots


def _references_decision_var(node: ast.AST, roots: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in roots
    if isinstance(node, ast.Subscript):
        return _references_decision_var(node.value, roots)
    if isinstance(node, ast.Attribute):
        return _references_decision_var(node.value, roots)
    return False
