"""Feedback uptake scoring for V3 semantic repair experiments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FeedbackUptakeItem:
    problem_id: str
    round_from: int
    round_to: int
    suggested_fix: str
    error_type: str
    implemented_next_round: bool | None
    implementation_evidence: str
    error_resolved: bool | None
    new_error_introduced: bool | None
    objective_gap_improved: bool | None
    eventual_solved: bool | None
    mode: str = "heuristic"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_feedback_uptake(
    previous_advisory_result: dict[str, Any] | None,
    previous_code: str,
    next_code: str,
    problem_statement: str,
    execution_before: dict[str, Any] | None,
    execution_after: dict[str, Any] | None,
    config: Any | None = None,
    optional_llm_client: Any | None = None,
    *,
    problem_id: str = "",
    round_from: int = 0,
    eventual_solved: bool | None = None,
) -> list[FeedbackUptakeItem]:
    del problem_statement, optional_llm_client
    mode = str(getattr(config, "feedback_uptake_mode", "heuristic") if config is not None else "heuristic")
    if mode == "off":
        return []
    instructions = _repair_instructions(previous_advisory_result)
    if not instructions:
        return []
    before_error = str((execution_before or {}).get("error_type") or "")
    after_error = str((execution_after or {}).get("error_type") or "")
    gap_before = _optional_float((execution_before or {}).get("objective_gap"))
    gap_after = _optional_float((execution_after or {}).get("objective_gap"))
    rows: list[FeedbackUptakeItem] = []
    for instruction in instructions:
        implemented, evidence = _heuristic_implemented(instruction, previous_code, next_code)
        rows.append(
            FeedbackUptakeItem(
                problem_id=problem_id,
                round_from=round_from,
                round_to=round_from + 1,
                suggested_fix=instruction,
                error_type=before_error,
                implemented_next_round=implemented,
                implementation_evidence=evidence,
                error_resolved=_resolved(before_error, after_error),
                new_error_introduced=_new_error(before_error, after_error),
                objective_gap_improved=(
                    gap_after < gap_before if gap_before is not None and gap_after is not None else None
                ),
                eventual_solved=eventual_solved,
                mode="heuristic" if mode == "llm" else mode,
            )
        )
    return rows


def summarize_feedback_uptake(items: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(items)
    implemented = sum(1 for item in items if item.get("implemented_next_round") is True)
    resolved = sum(1 for item in items if item.get("error_resolved") is True)
    new_error = sum(1 for item in items if item.get("new_error_introduced") is True)
    gap_improved = sum(1 for item in items if item.get("objective_gap_improved") is True)
    implemented_and_solved = sum(
        1
        for item in items
        if item.get("implemented_next_round") is True and item.get("eventual_solved") is True
    )
    return {
        "feedback_items_total": total,
        "feedback_items_implemented": implemented,
        "feedback_items_resolved": resolved,
        "feedback_new_error_count": new_error,
        "feedback_objective_gap_improved_count": gap_improved,
        "implementation_rate": implemented / total if total else None,
        "resolution_rate": resolved / total if total else None,
        "new_error_rate": new_error / total if total else None,
        "objective_gap_improvement_rate": gap_improved / total if total else None,
        "implemented_and_solved_count": implemented_and_solved,
    }


def _repair_instructions(previous_advisory_result: dict[str, Any] | None) -> list[str]:
    if not isinstance(previous_advisory_result, dict):
        return []
    instructions = previous_advisory_result.get("repair_instructions")
    if isinstance(instructions, list):
        return [str(item) for item in instructions if str(item).strip()]
    diagnosis = previous_advisory_result.get("advisory_diagnosis")
    if isinstance(diagnosis, dict) and isinstance(diagnosis.get("repair_instructions"), list):
        return [str(item) for item in diagnosis["repair_instructions"] if str(item).strip()]
    return []


def _heuristic_implemented(instruction: str, previous_code: str, next_code: str) -> tuple[bool | None, str]:
    lowered = instruction.lower()
    previous = previous_code.lower()
    new = next_code.lower()
    checks: list[tuple[bool, str]] = []
    if "flow conservation" in lowered or "equality" in lowered or "balance" in lowered:
        checks.append(("==" in new or " grb.equal" in new, "next code contains equality/balance-style constraints"))
    if "sold" in lowered:
        checks.append(("sold" in new and "sold" not in previous, "next code introduces sold variables"))
    if "objective" in lowered or "count only sold" in lowered:
        checks.append(("setobjective" in new and _objective_region(previous) != _objective_region(new), "objective code changed"))
    if "output" in lowered or "print" in lowered or "return" in lowered:
        checks.append((("print" in new or "return" in new) and new != previous, "output/return behavior changed"))
    if "route-flow" in lowered or "route flow" in lowered:
        checks.append(("route" in new and ("==" in new or "flow" in new), "route flow terms appear with equality/flow structure"))
    if not checks:
        changed = previous_code.strip() != next_code.strip()
        return (changed if next_code.strip() else None, "generic code changed" if changed else "no recognizable implementation signal")
    implemented = any(item[0] for item in checks)
    evidence = "; ".join(item[1] for item in checks if item[0]) or "expected implementation pattern not found"
    return implemented, evidence


def _objective_region(code: str) -> str:
    index = code.find("setobjective")
    if index < 0:
        return ""
    return code[index : index + 500]


def _resolved(before_error: str, after_error: str) -> bool | None:
    if not before_error:
        return None
    if not after_error:
        return True
    return before_error != after_error


def _new_error(before_error: str, after_error: str) -> bool | None:
    if not after_error:
        return False
    if not before_error:
        return True
    return before_error != after_error


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
