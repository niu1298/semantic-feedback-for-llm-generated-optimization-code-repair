"""Compare intended and extracted formulation specs into advisory diagnoses."""

from __future__ import annotations

import json
import uuid
from typing import Any

from .advisory import AdvisoryDiagnosis, DiagnosedError, parse_advisory_response
from .formulation_spec import FormulationSpec


def compare_formulation_specs(
    problem_statement: str,
    intended_spec: FormulationSpec,
    extracted_spec: FormulationSpec,
    generated_code: str,
    config: Any | None = None,
    llm_client: Any | None = None,
) -> AdvisoryDiagnosis:
    """Return normalized advisory diagnosis for spec mismatches.

    If an LLM client is supplied, use it. If it fails or is absent, use a
    conservative deterministic comparison so the pipeline can continue.
    """

    if llm_client is not None:
        messages = build_spec_comparison_prompt(
            problem_statement=problem_statement,
            intended_spec=intended_spec,
            extracted_spec=extracted_spec,
            generated_code=generated_code,
        )
        try:
            raw = _chat(llm_client, messages)
            return parse_advisory_response(
                raw,
                advisor_name=str(getattr(config, "spec_comparison_model", "") or "spec_comparison"),
            )
        except Exception:
            pass
    return heuristic_compare_formulation_specs(intended_spec, extracted_spec)


def build_spec_comparison_prompt(
    *,
    problem_statement: str,
    intended_spec: FormulationSpec,
    extracted_spec: FormulationSpec,
    generated_code: str,
) -> list[dict[str, str]]:
    schema = {
        "score": 0.0,
        "should_execute": True,
        "confidence": 0.0,
        "diagnosed_errors": [
            {
                "type": "missing_constraint | wrong_objective | variable_issue | domain_issue | output_issue | api_issue | runtime_risk | compile_risk | no_objective | other",
                "severity": "low | medium | high",
                "description": "string",
                "evidence": "string",
                "suggested_fix": "string",
            }
        ],
        "repair_instructions": ["string"],
        "reject_reasons": ["string"],
    }
    return [
        {
            "role": "system",
            "content": (
                "Compare optimization formulation specs. Return strict compact JSON only. "
                "Do not include prose or chain-of-thought. Keep every string short and single-line."
            ),
        },
        {
            "role": "user",
            "content": (
                "Identify mismatches between the intended formulation and what the generated code models. "
                "Look for missing variables, wrong domains, wrong objective direction/terms, double-counting, "
                "missing constraints, inequality/equality mismatch, missing output, flow continuity gaps, "
                "missing cost terms, and unconstrained objective variables.\n\n"
                f"Problem statement:\n{problem_statement.strip()}\n\n"
                f"Intended spec:\n{json.dumps(intended_spec.to_dict(), ensure_ascii=False)}\n\n"
                f"Extracted code spec:\n{json.dumps(extracted_spec.to_dict(), ensure_ascii=False)}\n\n"
                f"Generated code excerpt:\n```python\n{generated_code[:6000]}\n```\n\n"
                "JSON rules:\n"
                "- Return one valid JSON object only.\n"
                "- Use at most 5 diagnosed_errors and at most 5 repair_instructions.\n"
                "- Each repair instruction must be one short string, not a nested list or multi-step block.\n"
                "- Put formulas inside strings.\n"
                "- Do not put reject_reasons inside repair_instructions.\n"
                "- Do not use markdown, comments, or trailing prose.\n\n"
                f"Return JSON matching:\n{json.dumps(schema, ensure_ascii=False)}"
            ),
        },
    ]


def heuristic_compare_formulation_specs(
    intended_spec: FormulationSpec,
    extracted_spec: FormulationSpec,
) -> AdvisoryDiagnosis:
    errors: list[DiagnosedError] = []
    if (
        intended_spec.objective_direction() != "unknown"
        and extracted_spec.objective_direction() != "unknown"
        and intended_spec.objective_direction() != extracted_spec.objective_direction()
    ):
        errors.append(
            DiagnosedError(
                type="wrong_objective",
                severity="high",
                description=(
                    f"Objective direction differs: intended {intended_spec.objective_direction()} "
                    f"but code appears to {extracted_spec.objective_direction()}."
                ),
                suggested_fix="Correct the objective direction to match the intended formulation.",
            )
        )
    intended_constraints = _description_tokens(
        item.description or item.name or item.mathematical_form for item in intended_spec.constraints
    )
    extracted_constraints = _description_tokens(
        item.description or item.name or item.mathematical_form for item in extracted_spec.constraints
    )
    missing = sorted(intended_constraints - extracted_constraints)
    if intended_spec.constraint_count() and not extracted_spec.constraint_count():
        errors.append(
            DiagnosedError(
                type="missing_constraint",
                severity="high",
                description="The intended formulation has constraints but the extracted code spec has none.",
                suggested_fix="Add the missing constraints from the problem statement.",
            )
        )
    elif missing:
        errors.append(
            DiagnosedError(
                type="missing_constraint",
                severity="medium",
                description="Some intended constraint concepts are missing from the extracted code spec.",
                evidence=", ".join(missing[:8]),
                suggested_fix="Add or correct constraints covering the missing concepts.",
            )
        )
    if intended_spec.variable_count() and not extracted_spec.variable_count():
        errors.append(
            DiagnosedError(
                type="variable_issue",
                severity="high",
                description="The intended formulation has decision variables but none were extracted from code.",
                suggested_fix="Define the required decision variables with correct domains and indexing.",
            )
        )
    if intended_spec.output_requirements and not extracted_spec.output_requirements:
        errors.append(
            DiagnosedError(
                type="output_issue",
                severity="medium",
                description="Expected output requirements are absent from the extracted code spec.",
                suggested_fix="Return or print the objective value in the required harness format.",
            )
        )
    repair = [item.suggested_fix for item in errors if item.suggested_fix]
    score = 1.0 if not errors else max(0.0, 1.0 - 0.2 * len(errors))
    return AdvisoryDiagnosis(
        diagnosis_id=str(uuid.uuid4()),
        round=0,
        advisor_name="heuristic_spec_comparison",
        score=score,
        diagnosed_errors=errors,
        repair_instructions=repair,
        confidence=0.6 if errors else 0.8,
        reject_reasons=[item.description for item in errors if item.severity == "high"],
        should_execute=not any(item.severity == "high" for item in errors),
        raw_response="",
        status="ok",
        parse_success=True,
    )


def advisory_to_semantic_payload(diagnosis: AdvisoryDiagnosis) -> dict[str, Any]:
    missing = [item.description for item in diagnosis.diagnosed_errors if item.type == "missing_constraint"]
    variable = [
        item.description
        for item in diagnosis.diagnosed_errors
        if item.type in {"variable_issue", "domain_issue"}
    ]
    api = [item.description for item in diagnosis.diagnosed_errors if item.type == "api_issue"]
    output = [
        item.description
        for item in diagnosis.diagnosed_errors
        if item.type in {"output_issue", "no_objective"}
    ]
    return {
        "passed": diagnosis.should_execute and diagnosis.score >= 0.6,
        "skipped": False,
        "status": diagnosis.status,
        "score": diagnosis.score,
        "should_execute": diagnosis.should_execute,
        "missing_constraints": missing,
        "wrong_objective": any(item.type == "wrong_objective" for item in diagnosis.diagnosed_errors),
        "variable_issues": variable,
        "gurobi_api_issues": api,
        "output_issues": output,
        "feedback": "; ".join(diagnosis.repair_instructions),
        "raw_response": diagnosis.raw_response,
        "advisory_diagnosis": diagnosis.to_dict(),
        "diagnosed_error_types": [item.type for item in diagnosis.diagnosed_errors],
        "repair_instructions": list(diagnosis.repair_instructions),
        "confidence": diagnosis.confidence,
        "reject_reasons": list(diagnosis.reject_reasons),
        "parse_success": diagnosis.parse_success,
        "empty_response": diagnosis.empty_response,
        "parse_failure_type": diagnosis.parse_failure_type,
        "debug_metadata": diagnosis.parse_debug,
    }


def _chat(client: Any, messages: list[dict[str, str]]) -> str:
    if hasattr(client, "chat_with_metadata"):
        payload = client.chat_with_metadata(messages)
        return str(payload.get("text", ""))
    return str(client.chat(messages))


def _description_tokens(values: Any) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        for token in str(value).lower().replace("_", " ").split():
            stripped = "".join(ch for ch in token if ch.isalnum())
            if len(stripped) >= 5:
                tokens.add(stripped)
    return tokens
