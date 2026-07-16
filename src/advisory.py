"""Normalized advisory diagnosis parsing and compatibility helpers."""

from __future__ import annotations

import ast
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


ERROR_TYPES = {
    "missing_constraint",
    "wrong_objective",
    "variable_issue",
    "domain_issue",
    "output_issue",
    "api_issue",
    "runtime_risk",
    "compile_risk",
    "no_objective",
    "empty_response",
    "parse_failed",
    "other",
}
SEVERITIES = {"low", "medium", "high"}


@dataclass(frozen=True, slots=True)
class DiagnosedError:
    type: str
    severity: str = "medium"
    description: str = ""
    evidence: str = ""
    suggested_fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AdvisoryDiagnosis:
    diagnosis_id: str
    round: int
    advisor_name: str
    score: float
    diagnosed_errors: list[DiagnosedError] = field(default_factory=list)
    repair_instructions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    reject_reasons: list[str] = field(default_factory=list)
    should_execute: bool = True
    raw_response: str = ""
    status: str = "ok"
    parse_success: bool = True
    empty_response: bool = False
    parse_failure_type: str | None = None
    parse_debug: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["diagnosed_errors"] = [item.to_dict() for item in self.diagnosed_errors]
        return payload


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", flags=re.DOTALL | re.IGNORECASE)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")
_REJECT_REASONS_KEY_RE = re.compile(r",\s*(\"reject_reasons\"\s*:)")


def parse_advisory_response(
    raw_response: str,
    *,
    round_index: int = 0,
    advisor_name: str = "",
    parse_debug: dict[str, Any] | None = None,
) -> AdvisoryDiagnosis:
    """Parse and normalize advisory LLM output.

    The parser accepts the new schema, the historical schema, JSON in markdown
    fences, and a few minor JSON formatting mistakes. Complete parse failure
    still returns a valid diagnosis object that keeps the raw response.
    """

    debug = dict(parse_debug or {})
    if not raw_response.strip():
        return _parse_failed_diagnosis(
            raw_response=raw_response,
            round_index=round_index,
            advisor_name=advisor_name,
            failure_type="empty_response",
            parse_debug=debug,
        )

    try:
        payload = _load_json_payload(raw_response)
    except Exception:
        return _parse_failed_diagnosis(
            raw_response=raw_response,
            round_index=round_index,
            advisor_name=advisor_name,
            failure_type="invalid_json",
            parse_debug=debug,
        )
    if not isinstance(payload, dict):
        return _parse_failed_diagnosis(
            raw_response=raw_response,
            round_index=round_index,
            advisor_name=advisor_name,
            failure_type="invalid_json",
            parse_debug=debug,
        )
    return normalize_advisory_payload(
        payload,
        raw_response=raw_response,
        round_index=round_index,
        advisor_name=advisor_name,
        parse_debug=debug,
    )


def normalize_advisory_payload(
    payload: dict[str, Any],
    *,
    raw_response: str = "",
    round_index: int = 0,
    advisor_name: str = "",
    parse_debug: dict[str, Any] | None = None,
) -> AdvisoryDiagnosis:
    """Normalize new or legacy advisory payloads into AdvisoryDiagnosis."""

    diagnosed_errors = _normalize_diagnosed_errors(payload.get("diagnosed_errors"))
    legacy_errors = _legacy_errors(payload)
    diagnosed_errors.extend(legacy_errors)
    debug = dict(parse_debug or {})

    has_known_schema = any(
        key in payload
        for key in (
            "score",
            "should_execute",
            "diagnosed_errors",
            "repair_instructions",
            "feedback",
            "missing_constraints",
            "wrong_objective",
            "variable_issues",
            "gurobi_api_issues",
            "output_issues",
        )
    )
    if not has_known_schema:
        return _parse_failed_diagnosis(
            raw_response=raw_response,
            round_index=round_index,
            advisor_name=advisor_name,
            failure_type="schema_missing_fields",
            parse_debug=debug,
        )

    score = _clamp_float(payload.get("score"), default=0.0)
    confidence = _clamp_float(payload.get("confidence"), default=score)
    repair_instructions = _string_list(payload.get("repair_instructions"))
    feedback = str(payload.get("feedback", "") or "").strip()
    if feedback and feedback not in repair_instructions:
        repair_instructions.append(feedback)

    reject_reasons = _string_list(payload.get("reject_reasons"))
    should_execute = bool(payload.get("should_execute", True))
    if not should_execute and not reject_reasons:
        reject_reasons = _default_reject_reasons(diagnosed_errors)
    if not repair_instructions and diagnosed_errors:
        repair_instructions = [
            error.suggested_fix or error.description
            for error in diagnosed_errors
            if error.suggested_fix or error.description
        ]

    return AdvisoryDiagnosis(
        diagnosis_id=str(payload.get("diagnosis_id") or uuid.uuid4()),
        round=int(payload.get("round", round_index) or 0),
        advisor_name=str(payload.get("advisor_name") or advisor_name),
        score=score,
        diagnosed_errors=diagnosed_errors,
        repair_instructions=repair_instructions,
        confidence=confidence,
        reject_reasons=reject_reasons,
        should_execute=should_execute,
        raw_response=raw_response,
        status=str(payload.get("status") or "ok"),
        parse_success=True,
        empty_response=False,
        parse_failure_type=None,
        parse_debug=debug,
    )


def diagnosis_to_legacy_fields(diagnosis: AdvisoryDiagnosis) -> dict[str, Any]:
    """Map normalized diagnosis back to fields used by older result code."""

    missing_constraints = [
        item.description
        for item in diagnosis.diagnosed_errors
        if item.type == "missing_constraint"
    ]
    variable_issues = [
        item.description
        for item in diagnosis.diagnosed_errors
        if item.type in {"variable_issue", "domain_issue"}
    ]
    gurobi_api_issues = [
        item.description
        for item in diagnosis.diagnosed_errors
        if item.type == "api_issue"
    ]
    output_issues = [
        item.description
        for item in diagnosis.diagnosed_errors
        if item.type in {"output_issue", "no_objective"}
    ]
    wrong_objective = any(item.type == "wrong_objective" for item in diagnosis.diagnosed_errors)
    feedback = "; ".join(diagnosis.repair_instructions)
    return {
        "missing_constraints": missing_constraints,
        "wrong_objective": wrong_objective,
        "variable_issues": variable_issues,
        "gurobi_api_issues": gurobi_api_issues,
        "output_issues": output_issues,
        "feedback": feedback,
    }


def _load_json_payload(raw_response: str) -> Any:
    candidates = [raw_response]
    candidates.extend(match.group(1) for match in _FENCED_JSON_RE.finditer(raw_response))
    candidates.extend(_balanced_json_object_candidates(raw_response))
    start = raw_response.find("{")
    if start >= 0:
        candidates.append(raw_response[start:])

    fallback_payload: Any = None
    for candidate in _dedupe_candidates(candidates):
        candidate = candidate.strip()
        if not candidate:
            continue
        for fixed in _json_variants(candidate):
            try:
                payload = json.loads(fixed)
                if _has_advisory_schema_keys(payload):
                    return payload
                if fallback_payload is None:
                    fallback_payload = payload
                continue
            except json.JSONDecodeError:
                pass
            try:
                decoder = json.JSONDecoder()
                payload, _ = decoder.raw_decode(fixed)
                if _has_advisory_schema_keys(payload):
                    return payload
                if fallback_payload is None:
                    fallback_payload = payload
                continue
            except json.JSONDecodeError:
                pass
            try:
                payload = ast.literal_eval(fixed)
                if _has_advisory_schema_keys(payload):
                    return payload
                if fallback_payload is None:
                    fallback_payload = payload
            except (SyntaxError, ValueError):
                pass
    if fallback_payload is not None:
        return fallback_payload
    raise json.JSONDecodeError("No JSON object found", raw_response, 0)


def _json_variants(text: str) -> list[str]:
    stripped = text.strip()
    variants = _variant_repairs(stripped)
    repaired_overescaped = stripped.replace('\\"', '"')
    if repaired_overescaped != stripped:
        variants.extend(_variant_repairs(repaired_overescaped))
    variants = _dedupe_candidates(variants)
    return variants


def _variant_repairs(text: str) -> list[str]:
    variants = [text]
    without_trailing_commas = _TRAILING_COMMA_RE.sub(r"\1", text)
    if without_trailing_commas != text:
        variants.append(without_trailing_commas)
    closed_repair_instructions = _repair_missing_repair_instructions_closure(text)
    if closed_repair_instructions != text:
        variants.append(closed_repair_instructions)
        closed_without_trailing_commas = _TRAILING_COMMA_RE.sub(r"\1", closed_repair_instructions)
        if closed_without_trailing_commas != closed_repair_instructions:
            variants.append(closed_without_trailing_commas)
    return variants


def _repair_missing_repair_instructions_closure(text: str) -> str:
    if '"repair_instructions"' not in text or '],"reject_reasons"' in text:
        return text
    return _REJECT_REASONS_KEY_RE.sub(r'],\1', text, count=1)


def _balanced_json_object_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(text[start : index + 1])
                start = None
    candidates.sort(key=len, reverse=True)
    return candidates


def _dedupe_candidates(candidates: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        text = candidate.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _has_advisory_schema_keys(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    return any(
        key in payload
        for key in (
            "score",
            "should_execute",
            "diagnosed_errors",
            "repair_instructions",
            "feedback",
            "missing_constraints",
            "wrong_objective",
            "variable_issues",
            "gurobi_api_issues",
            "output_issues",
        )
    )


def _normalize_diagnosed_errors(value: Any) -> list[DiagnosedError]:
    if not isinstance(value, list):
        return []
    errors: list[DiagnosedError] = []
    for item in value:
        if isinstance(item, str):
            errors.append(DiagnosedError(type="other", description=item))
            continue
        if not isinstance(item, dict):
            continue
        errors.append(
            DiagnosedError(
                type=_normalize_error_type(item.get("type")),
                severity=_normalize_severity(item.get("severity")),
                description=str(item.get("description") or ""),
                evidence=str(item.get("evidence") or ""),
                suggested_fix=str(item.get("suggested_fix") or ""),
            )
        )
    return errors


def _legacy_errors(payload: dict[str, Any]) -> list[DiagnosedError]:
    errors: list[DiagnosedError] = []
    for description in _string_list(payload.get("missing_constraints")):
        errors.append(
            DiagnosedError(
                type="missing_constraint",
                severity="high",
                description=description,
                suggested_fix=description,
            )
        )
    if bool(payload.get("wrong_objective", False)):
        errors.append(
            DiagnosedError(
                type="wrong_objective",
                severity="high",
                description="Objective direction or expression may be wrong.",
                evidence=str(payload.get("feedback") or ""),
                suggested_fix="Correct the objective direction and objective expression.",
            )
        )
    for description in _string_list(payload.get("variable_issues")):
        errors.append(
            DiagnosedError(
                type="variable_issue",
                severity="medium",
                description=description,
                suggested_fix=description,
            )
        )
    for description in _string_list(payload.get("gurobi_api_issues")):
        errors.append(
            DiagnosedError(
                type="api_issue",
                severity="medium",
                description=description,
                suggested_fix=description,
            )
        )
    for description in _string_list(payload.get("output_issues")):
        errors.append(
            DiagnosedError(
                type="output_issue",
                severity="medium",
                description=description,
                suggested_fix=description,
            )
        )
    return errors


def _parse_failed_diagnosis(
    *,
    raw_response: str,
    round_index: int,
    advisor_name: str,
    failure_type: str,
    parse_debug: dict[str, Any] | None = None,
) -> AdvisoryDiagnosis:
    if failure_type == "empty_response":
        error_type = "empty_response"
        description = "Semantic advisor returned an empty response."
        suggested_fix = "Semantic diagnosis unavailable; use execution feedback."
    elif failure_type == "schema_missing_fields":
        error_type = "parse_failed"
        description = "Semantic advisor returned JSON that did not match the advisory schema."
        suggested_fix = "Semantic diagnosis unavailable; use execution feedback."
    else:
        error_type = "parse_failed"
        description = "Semantic advisor output was not valid JSON."
        suggested_fix = "Semantic diagnosis unavailable; use execution feedback."
    return AdvisoryDiagnosis(
        diagnosis_id=str(uuid.uuid4()),
        round=round_index,
        advisor_name=advisor_name,
        score=0.0,
        diagnosed_errors=[
            DiagnosedError(
                type=error_type,
                severity="medium",
                description=description,
                evidence=raw_response[:500],
                suggested_fix=suggested_fix,
            )
        ],
        repair_instructions=[suggested_fix],
        confidence=0.0,
        reject_reasons=[],
        should_execute=True,
        raw_response=raw_response,
        status=failure_type,
        parse_success=False,
        empty_response=failure_type == "empty_response",
        parse_failure_type=failure_type,
        parse_debug=dict(parse_debug or {}),
    )


def _default_reject_reasons(errors: list[DiagnosedError]) -> list[str]:
    reasons = [item.description for item in errors if item.severity in {"medium", "high"} and item.description]
    return reasons[:5]


def _normalize_error_type(value: Any) -> str:
    text = str(value or "other").strip()
    return text if text in ERROR_TYPES else "other"


def _normalize_severity(value: Any) -> str:
    text = str(value or "medium").strip().lower()
    return text if text in SEVERITIES else "medium"


def _clamp_float(value: Any, *, default: float) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return default
    return min(1.0, max(0.0, score))


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value]
    return []
