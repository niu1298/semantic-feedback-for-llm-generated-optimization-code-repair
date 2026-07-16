"""Shared formulation-spec schema and robust parser for V3 expansion."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", flags=re.DOTALL | re.IGNORECASE)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


@dataclass(frozen=True, slots=True)
class DecisionVariableSpec:
    name: str = ""
    meaning: str = ""
    indexing: str = ""
    domain: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ObjectiveTermSpec:
    description: str = ""
    coefficient_or_formula: str = ""
    variables_involved: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ObjectiveSpec:
    direction: str = "unknown"
    terms: list[ObjectiveTermSpec] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["terms"] = [term.to_dict() for term in self.terms]
        return payload


@dataclass(frozen=True, slots=True)
class ConstraintSpec:
    name: str = ""
    description: str = ""
    mathematical_form: str = ""
    sense: str = "unknown"
    variables_involved: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FormulationSpec:
    problem_id: str = ""
    source: str = "unknown"
    problem_type: str = "unknown"
    sense: str = "unknown"
    decision_variables: list[DecisionVariableSpec] = field(default_factory=list)
    objective: ObjectiveSpec = field(default_factory=ObjectiveSpec)
    constraints: list[ConstraintSpec] = field(default_factory=list)
    output_requirements: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "source": self.source,
            "problem_type": self.problem_type,
            "sense": self.sense,
            "decision_variables": [item.to_dict() for item in self.decision_variables],
            "objective": self.objective.to_dict(),
            "constraints": [item.to_dict() for item in self.constraints],
            "output_requirements": list(self.output_requirements),
            "notes": self.notes,
        }

    def variable_count(self) -> int:
        return len(self.decision_variables)

    def constraint_count(self) -> int:
        return len(self.constraints)

    def objective_direction(self) -> str:
        return self.objective.direction or self.sense or "unknown"

    def variable_names(self) -> list[str]:
        return [item.name for item in self.decision_variables if item.name]

    def constraint_senses(self) -> list[str]:
        return [item.sense for item in self.constraints if item.sense]

    def compact_text(self, *, max_constraints: int = 12) -> str:
        variables = "; ".join(
            f"{item.name} ({item.domain}): {item.meaning}" for item in self.decision_variables
        )
        terms = "; ".join(
            f"{item.description} [{item.coefficient_or_formula}]"
            for item in self.objective.terms
        )
        constraints = "; ".join(
            f"{item.name or 'constraint'} {item.sense}: {item.description or item.mathematical_form}"
            for item in self.constraints[:max_constraints]
        )
        if len(self.constraints) > max_constraints:
            constraints += f"; ... {len(self.constraints) - max_constraints} more"
        outputs = "; ".join(self.output_requirements)
        return (
            f"Formulation spec ({self.source}, {self.problem_type}): "
            f"sense={self.objective_direction()}; variables={variables or 'unknown'}; "
            f"objective_terms={terms or 'unknown'}; constraints={constraints or 'unknown'}; "
            f"outputs={outputs or 'return objective value'}; notes={self.notes}"
        )


@dataclass(frozen=True, slots=True)
class FormulationSpecResult:
    spec: FormulationSpec
    raw_response: str = ""
    parse_success: bool = True
    empty_response: bool = False
    parse_failure_type: str | None = None
    parse_debug: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec.to_dict(),
            "raw_response": self.raw_response,
            "parse_success": self.parse_success,
            "empty_response": self.empty_response,
            "parse_failure_type": self.parse_failure_type,
            "parse_debug": dict(self.parse_debug),
            "variable_count": self.spec.variable_count(),
            "constraint_count": self.spec.constraint_count(),
            "objective_direction": self.spec.objective_direction(),
        }


def parse_formulation_spec_response(
    raw_response: str,
    *,
    problem_id: str = "",
    source: str = "unknown",
    parse_debug: dict[str, Any] | None = None,
) -> FormulationSpecResult:
    debug = dict(parse_debug or {})
    if not raw_response.strip():
        return _fallback_result(
            raw_response=raw_response,
            problem_id=problem_id,
            source=source,
            failure_type="empty_response",
            debug=debug,
        )
    try:
        payload = _load_json_payload(raw_response)
    except Exception:
        return _fallback_result(
            raw_response=raw_response,
            problem_id=problem_id,
            source=source,
            failure_type="invalid_json",
            debug=debug,
        )
    if not isinstance(payload, dict):
        return _fallback_result(
            raw_response=raw_response,
            problem_id=problem_id,
            source=source,
            failure_type="invalid_json",
            debug=debug,
        )
    if not _has_minimum_schema(payload):
        return _fallback_result(
            raw_response=raw_response,
            problem_id=problem_id,
            source=source,
            failure_type="schema_missing_fields",
            debug=debug,
        )
    return FormulationSpecResult(
        spec=normalize_formulation_spec_payload(payload, problem_id=problem_id, source=source),
        raw_response=raw_response,
        parse_success=True,
        empty_response=False,
        parse_failure_type=None,
        parse_debug=debug,
    )


def normalize_formulation_spec_payload(
    payload: dict[str, Any],
    *,
    problem_id: str = "",
    source: str = "unknown",
) -> FormulationSpec:
    objective_payload = payload.get("objective") if isinstance(payload.get("objective"), dict) else {}
    return FormulationSpec(
        problem_id=str(payload.get("problem_id") or problem_id),
        source=str(payload.get("source") or source),
        problem_type=_normalize_choice(payload.get("problem_type"), {"LP", "ILP", "MILP", "NLP", "unknown"}),
        sense=_normalize_choice(payload.get("sense"), {"minimize", "maximize", "unknown"}),
        decision_variables=_parse_variables(payload.get("decision_variables")),
        objective=ObjectiveSpec(
            direction=_normalize_choice(
                objective_payload.get("direction") or payload.get("sense"),
                {"minimize", "maximize", "unknown"},
            ),
            terms=_parse_objective_terms(objective_payload.get("terms")),
        ),
        constraints=_parse_constraints(payload.get("constraints")),
        output_requirements=_string_list(payload.get("output_requirements")),
        notes=str(payload.get("notes") or ""),
    )


def fallback_formulation_spec(
    *,
    problem_id: str = "",
    source: str = "unknown",
    notes: str = "",
) -> FormulationSpec:
    return FormulationSpec(problem_id=problem_id, source=source, notes=notes)


def _fallback_result(
    *,
    raw_response: str,
    problem_id: str,
    source: str,
    failure_type: str,
    debug: dict[str, Any],
) -> FormulationSpecResult:
    return FormulationSpecResult(
        spec=fallback_formulation_spec(
            problem_id=problem_id,
            source=source,
            notes=f"Formulation spec unavailable: {failure_type}.",
        ),
        raw_response=raw_response,
        parse_success=False,
        empty_response=failure_type == "empty_response",
        parse_failure_type=failure_type,
        parse_debug=debug,
    )


def _load_json_payload(raw_response: str) -> Any:
    candidates = [raw_response]
    candidates.extend(match.group(1) for match in _FENCED_JSON_RE.finditer(raw_response))
    candidates.extend(_balanced_json_object_candidates(raw_response))
    start = raw_response.find("{")
    if start >= 0:
        candidates.append(raw_response[start:])
    unique_candidates = sorted({candidate.strip() for candidate in candidates if candidate.strip()}, key=len, reverse=True)
    for candidate in unique_candidates:
        for variant in _json_variants(candidate):
            try:
                return json.loads(variant)
            except json.JSONDecodeError:
                pass
            try:
                decoder = json.JSONDecoder()
                payload, _ = decoder.raw_decode(variant)
                return payload
            except json.JSONDecodeError:
                pass
            try:
                return ast.literal_eval(variant)
            except (SyntaxError, ValueError):
                pass
    raise json.JSONDecodeError("No JSON object found", raw_response, 0)


def _balanced_json_object_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
            continue
        if char == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(text[start : index + 1])
                start = None
    return candidates


def _json_variants(text: str) -> list[str]:
    stripped = text.strip()
    variants = [stripped]
    fixed = _TRAILING_COMMA_RE.sub(r"\1", stripped)
    if fixed != stripped:
        variants.append(fixed)
    return variants


def _has_minimum_schema(payload: dict[str, Any]) -> bool:
    return any(
        key in payload
        for key in (
            "decision_variables",
            "objective",
            "constraints",
            "output_requirements",
            "problem_type",
            "sense",
        )
    )


def _parse_variables(value: Any) -> list[DecisionVariableSpec]:
    items: list[DecisionVariableSpec] = []
    if not isinstance(value, list):
        return items
    for raw in value:
        if isinstance(raw, str):
            items.append(DecisionVariableSpec(name=raw))
        elif isinstance(raw, dict):
            items.append(
                DecisionVariableSpec(
                    name=str(raw.get("name") or ""),
                    meaning=str(raw.get("meaning") or ""),
                    indexing=str(raw.get("indexing") or ""),
                    domain=str(raw.get("domain") or "unknown"),
                )
            )
    return items


def _parse_objective_terms(value: Any) -> list[ObjectiveTermSpec]:
    items: list[ObjectiveTermSpec] = []
    if not isinstance(value, list):
        return items
    for raw in value:
        if isinstance(raw, str):
            items.append(ObjectiveTermSpec(description=raw))
        elif isinstance(raw, dict):
            items.append(
                ObjectiveTermSpec(
                    description=str(raw.get("description") or ""),
                    coefficient_or_formula=str(raw.get("coefficient_or_formula") or ""),
                    variables_involved=_string_list(raw.get("variables_involved")),
                )
            )
    return items


def _parse_constraints(value: Any) -> list[ConstraintSpec]:
    items: list[ConstraintSpec] = []
    if not isinstance(value, list):
        return items
    for raw in value:
        if isinstance(raw, str):
            items.append(ConstraintSpec(description=raw))
        elif isinstance(raw, dict):
            items.append(
                ConstraintSpec(
                    name=str(raw.get("name") or ""),
                    description=str(raw.get("description") or ""),
                    mathematical_form=str(raw.get("mathematical_form") or ""),
                    sense=_normalize_choice(raw.get("sense"), {"<=", ">=", "==", "unknown", "other"}),
                    variables_involved=_string_list(raw.get("variables_involved")),
                )
            )
    return items


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _normalize_choice(value: Any, allowed: set[str]) -> str:
    text = str(value or "unknown").strip()
    lowered = text.lower()
    for item in allowed:
        if lowered == item.lower():
            return item
    return "unknown" if "unknown" in allowed else text
