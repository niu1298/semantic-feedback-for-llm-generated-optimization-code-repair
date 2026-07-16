"""Multi-advisor aggregation helpers for optional V3 expansion."""

from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

from .advisory import AdvisoryDiagnosis, DiagnosedError


def aggregate_advisory_diagnoses(
    diagnoses: list[AdvisoryDiagnosis],
    *,
    aggregation: str = "single",
    advisor_name: str = "aggregated",
) -> AdvisoryDiagnosis:
    if not diagnoses:
        return AdvisoryDiagnosis(
            diagnosis_id=str(uuid.uuid4()),
            round=0,
            advisor_name=advisor_name,
            score=0.0,
            should_execute=True,
            parse_success=True,
            status="no_advisors",
        )
    if aggregation == "single":
        return diagnoses[0]
    if aggregation not in {"union", "majority", "pessimistic", "optimistic", "disagreement_escalation"}:
        raise ValueError("advisor_aggregation must be one of: single, union, majority, pessimistic, optimistic, disagreement_escalation")

    selected_errors = _select_errors(diagnoses, aggregation)
    repair_instructions = _dedupe(
        instruction for diagnosis in diagnoses for instruction in diagnosis.repair_instructions
    )
    reject_reasons = _dedupe(reason for diagnosis in diagnoses for reason in diagnosis.reject_reasons)
    should_execute = _aggregate_should_execute(diagnoses, aggregation)
    confidence = sum(diagnosis.confidence for diagnosis in diagnoses) / len(diagnoses)
    score = sum(diagnosis.score for diagnosis in diagnoses) / len(diagnoses)
    return AdvisoryDiagnosis(
        diagnosis_id=str(uuid.uuid4()),
        round=diagnoses[0].round,
        advisor_name=advisor_name,
        score=score,
        diagnosed_errors=selected_errors,
        repair_instructions=repair_instructions,
        confidence=confidence,
        reject_reasons=reject_reasons,
        should_execute=should_execute,
        raw_response="",
        status="ok",
        parse_success=all(diagnosis.parse_success for diagnosis in diagnoses),
        empty_response=any(diagnosis.empty_response for diagnosis in diagnoses),
        parse_failure_type=None,
        parse_debug=multi_advisor_debug(diagnoses),
    )


def multi_advisor_debug(diagnoses: list[AdvisoryDiagnosis]) -> dict[str, Any]:
    advisor_names = [diagnosis.advisor_name for diagnosis in diagnoses]
    should_execute = {diagnosis.advisor_name: diagnosis.should_execute for diagnosis in diagnoses}
    types_by_advisor = {
        diagnosis.advisor_name: [item.type for item in diagnosis.diagnosed_errors]
        for diagnosis in diagnoses
    }
    all_types = [error_type for values in types_by_advisor.values() for error_type in values]
    overlap = {
        error_type: count
        for error_type, count in Counter(all_types).items()
        if count > 1
    }
    return {
        "advisor_count": len(diagnoses),
        "advisor_names": advisor_names,
        "should_execute_by_advisor": should_execute,
        "should_execute_disagreement": len(set(should_execute.values())) > 1,
        "diagnosed_error_types_by_advisor": types_by_advisor,
        "unique_error_types_by_advisor": {
            key: sorted(set(values)) for key, values in types_by_advisor.items()
        },
        "advisor_error_type_overlap": overlap,
        "merged_diagnosed_error_types": sorted(set(all_types)),
    }


def _select_errors(diagnoses: list[AdvisoryDiagnosis], aggregation: str) -> list[DiagnosedError]:
    if aggregation == "majority" and len(diagnoses) >= 2:
        counts = Counter(error.type for diagnosis in diagnoses for error in diagnosis.diagnosed_errors)
        majority_types = {error_type for error_type, count in counts.items() if count >= 2}
        return _dedupe_errors(
            error for diagnosis in diagnoses for error in diagnosis.diagnosed_errors if error.type in majority_types
        )
    return _dedupe_errors(error for diagnosis in diagnoses for error in diagnosis.diagnosed_errors)


def _aggregate_should_execute(diagnoses: list[AdvisoryDiagnosis], aggregation: str) -> bool:
    values = [diagnosis.should_execute for diagnosis in diagnoses]
    if aggregation == "pessimistic":
        return all(values)
    if aggregation == "optimistic":
        return any(values)
    if aggregation == "majority":
        return sum(1 for value in values if value) >= (len(values) / 2)
    return values[0] if aggregation == "single" else all(values)


def _dedupe(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _dedupe_errors(values: Any) -> list[DiagnosedError]:
    seen: set[tuple[str, str]] = set()
    result: list[DiagnosedError] = []
    for error in values:
        key = (error.type, error.description)
        if key in seen:
            continue
        seen.add(key)
        result.append(error)
    return result
