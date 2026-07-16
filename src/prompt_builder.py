"""Prompt builder for vanilla optimization autoformulation."""

from __future__ import annotations

import json
import re


def build_vanilla_prompt(
    problem_text: str,
    dataset_name: str = "logior",
    problem_id: str | None = None,
    formulation_spec_text: str | None = None,
) -> list[dict]:
    label = dataset_name if problem_id is None else f"{dataset_name}/{problem_id}"
    spec_section = ""
    if formulation_spec_text:
        spec_section = (
            "Intended formulation spec (advisory, generated from the problem text):\n"
            f"{formulation_spec_text.strip()}\n\n"
        )
    return [
        {
            "role": "system",
            "content": (
                "You are an expert optimization modeler. Return only executable Python code. "
                "Do not include prose, markdown explanation, or analysis."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Problem source: {label}\n\n"
                f"Problem text:\n{problem_text.strip()}\n\n"
                f"{spec_section}"
                "Read the problem text and build a gurobipy model if appropriate. "
                "Identify the decision variables, constraints, and objective in code comments only if useful. "
                "Define a function named def solve(): or def solve_model():. "
                "The function should build and optimize the model and return the objective value, or None if no "
                "feasible optimal solution exists. Include all imports. Do not call the function at the end. "
                "Do not include API keys or external file dependencies. "
                "Return exactly one Python code block and nothing else."
            ),
        },
    ]


def build_repair_prompt(
    problem_text: str,
    previous_code: str,
    feedback: dict,
    *,
    include_execution_feedback: bool = True,
    include_static_checks: bool = True,
    include_semantic_diagnosis: bool = True,
    formulation_spec_text: str | None = None,
    extracted_spec_text: str | None = None,
    spec_comparison_text: str | None = None,
    compress_semantic_feedback: bool = False,
    compression_policy: str = "fixed",
    repair_feedback_max_chars: int | None = None,
    repair_feedback_max_items: int | None = None,
    adaptive_repair_feedback_max_chars: int | None = None,
    adaptive_repair_feedback_max_items: int | None = None,
    preserve_all_missing_constraint: bool = False,
    preserve_all_wrong_objective: bool = False,
    preserve_variable_and_constraint_names: bool = False,
    preserve_one_freeform_instruction: bool = False,
    preserve_error_type_conditioned_feedback: bool = False,
    semantic_feedback_priority_order: list[str] | None = None,
) -> list[dict]:
    feedback_text = build_repair_feedback_text(
        feedback,
        include_execution_feedback=include_execution_feedback,
        include_static_checks=include_static_checks,
        include_semantic_diagnosis=include_semantic_diagnosis,
        compress_semantic_feedback=compress_semantic_feedback,
        compression_policy=compression_policy,
        repair_feedback_max_chars=repair_feedback_max_chars,
        repair_feedback_max_items=repair_feedback_max_items,
        adaptive_repair_feedback_max_chars=adaptive_repair_feedback_max_chars,
        adaptive_repair_feedback_max_items=adaptive_repair_feedback_max_items,
        preserve_all_missing_constraint=preserve_all_missing_constraint,
        preserve_all_wrong_objective=preserve_all_wrong_objective,
        preserve_variable_and_constraint_names=preserve_variable_and_constraint_names,
        preserve_one_freeform_instruction=preserve_one_freeform_instruction,
        preserve_error_type_conditioned_feedback=preserve_error_type_conditioned_feedback,
        semantic_feedback_priority_order=semantic_feedback_priority_order,
    )
    task_instruction = _repair_task_instruction(str(feedback.get("error_type")))
    spec_context = (
        ""
        if compress_semantic_feedback
        else _repair_spec_context(
            formulation_spec_text=formulation_spec_text,
            extracted_spec_text=extracted_spec_text,
            spec_comparison_text=spec_comparison_text,
        )
    )
    return [
        {
            "role": "system",
            "content": (
                "You are an expert optimization modeler. Return only executable Python code. "
                "Do not include prose, markdown explanation, or analysis."
            ),
        },
        {
            "role": "user",
            "content": (
                f"{task_instruction}\n\n"
                f"Problem text:\n{problem_text.strip()}\n\n"
                f"{spec_context}"
                f"Previous code:\n```python\n{previous_code.strip()}\n```\n\n"
                f"{feedback_text}\n\n"
                "Do not repeat the previous code unchanged.\n\n"
                f"{_execution_output_contract()}\n\n"
                "Return exactly one Python code block and no prose. Include all imports. "
                "Define solve() or solve_model(). Do not call the function at import time. "
                "The function should build and optimize the model and return the numeric objective value."
            ),
        },
    ]


def build_semantic_judge_prompt(
    problem_text: str,
    generated_code: str,
    static_checks: dict | list[dict] | None = None,
    prompt_style: str = "default",
) -> list[dict]:
    schema = {
        "diagnosis_id": "optional string",
        "round": "integer",
        "advisor_name": "string",
        "score": "float between 0 and 1",
        "diagnosed_errors": [
            {
                "type": (
                    "missing_constraint | wrong_objective | variable_issue | domain_issue | "
                    "output_issue | api_issue | runtime_risk | compile_risk | no_objective | other"
                ),
                "severity": "low | medium | high",
                "description": "string",
                "evidence": "string",
                "suggested_fix": "string",
            }
        ],
        "repair_instructions": ["string"],
        "confidence": "float between 0 and 1",
        "reject_reasons": ["string"],
        "should_execute": "bool; false only when the code is clearly not worth executing",
    }
    if prompt_style == "compact":
        return _build_compact_semantic_judge_prompt(
            problem_text=problem_text,
            generated_code=generated_code,
            static_checks=static_checks,
        )
    if prompt_style != "default":
        raise ValueError("prompt_style must be one of: default, compact")

    static_section = ""
    if static_checks:
        static_section = (
            "\nStatic/rule-check findings (heuristic, not proof):\n"
            f"{json.dumps(static_checks, indent=2, ensure_ascii=False)}\n"
        )
    return [
        {
            "role": "system",
            "content": (
                "You are a strict optimization-formulation diagnostic reviewer. Return strict JSON only. "
                "Do not include markdown, prose, code fences, or comments outside the JSON object. "
                "Diagnose formulation errors separately from execution gating. Static checks are heuristic and "
                "not proof of correctness. Focus on missing constraints, wrong objective, wrong domains, output "
                "behavior, and Gurobi API risks. Keep strings compact. Do not include chain-of-thought."
            ),
        },
        {
            "role": "user",
            "content": (
                "Check whether the generated gurobipy code correctly represents the optimization problem.\n\n"
                "Review these points:\n"
                "- Are decision variables sufficient?\n"
                "- Are all constraints from the problem represented?\n"
                "- Is the objective direction correct?\n"
                "- Is the objective expression correct?\n"
                "- Are Gurobi API calls suspicious?\n"
                "- Does the code return an objective value?\n"
                "- Does it likely misuse addConstrs/addConstr?\n"
                "- Does it likely use nonlinear products without linearization when the problem should be MILP/ILP?\n\n"
                f"Problem text:\n{problem_text.strip()}\n\n"
                f"Generated code:\n```python\n{generated_code.strip()}\n```\n\n"
                f"{static_section}"
                "Return exactly one compact JSON object matching this schema. "
                "Use JSON booleans true/false and arrays. Summarize, do not reason aloud. "
                "Set should_execute=false only for clear compile/runtime risks or severe semantic defects; "
                "diagnosis will be used for repair even when execution proceeds:\n"
                f"{json.dumps(schema, indent=2)}"
            ),
        },
    ]


def _build_compact_semantic_judge_prompt(
    *,
    problem_text: str,
    generated_code: str,
    static_checks: dict | list[dict] | None = None,
) -> list[dict]:
    static_section = ""
    compact_static = _compact_static_checks_for_prompt(static_checks)
    if compact_static:
        static_section = (
            "\nHeuristic static warnings, not proof:\n"
            f"{json.dumps(compact_static, ensure_ascii=False)}\n"
        )
    schema = (
        '{"score":0.0,"should_execute":true,"confidence":0.0,'
        '"diagnosed_errors":[{"type":"missing_constraint|wrong_objective|variable_issue|'
        'domain_issue|output_issue|api_issue|runtime_risk|compile_risk|no_objective|other",'
        '"severity":"low|medium|high","description":"","evidence":"","suggested_fix":""}],'
        '"repair_instructions":[],"reject_reasons":[]}'
    )
    return [
        {
            "role": "system",
            "content": (
                "Return one valid compact JSON object only. No markdown. No prose. "
                "Do not reason aloud. Do not double-escape JSON keys, strings, or array items. "
                "Diagnose optimization formulation errors."
            ),
        },
        {
            "role": "user",
            "content": (
                "Judge whether this gurobipy code matches the problem. Focus only on missing constraints, "
                "wrong objective, wrong domains, API/output risks, and severe runtime risks. "
                "Set should_execute=false only for severe defects or clear compile/runtime risk.\n\n"
                f"Problem:\n{problem_text.strip()}\n\n"
                f"Code:\n```python\n{generated_code.strip()}\n```\n"
                f"{static_section}"
                "Use short strings. Do not emit escaped JSON fragments such as {\\\"type\\\":...}; "
                f"JSON schema exactly like this, with compact strings:\n{schema}"
            ),
        },
    ]


def build_repair_feedback_text(
    feedback: dict,
    *,
    include_execution_feedback: bool = True,
    include_static_checks: bool = True,
    include_semantic_diagnosis: bool = True,
    compress_semantic_feedback: bool = False,
    compression_policy: str = "fixed",
    repair_feedback_max_chars: int | None = None,
    repair_feedback_max_items: int | None = None,
    adaptive_repair_feedback_max_chars: int | None = None,
    adaptive_repair_feedback_max_items: int | None = None,
    preserve_all_missing_constraint: bool = False,
    preserve_all_wrong_objective: bool = False,
    preserve_variable_and_constraint_names: bool = False,
    preserve_one_freeform_instruction: bool = False,
    preserve_error_type_conditioned_feedback: bool = False,
    semantic_feedback_priority_order: list[str] | None = None,
) -> str:
    if compress_semantic_feedback:
        if compression_policy == "adaptive":
            return build_adaptive_compressed_repair_feedback_text(
                feedback,
                include_execution_feedback=include_execution_feedback,
                include_static_checks=include_static_checks,
                include_semantic_diagnosis=include_semantic_diagnosis,
                repair_feedback_max_chars=adaptive_repair_feedback_max_chars
                if adaptive_repair_feedback_max_chars is not None
                else repair_feedback_max_chars,
                repair_feedback_max_items=adaptive_repair_feedback_max_items
                if adaptive_repair_feedback_max_items is not None
                else repair_feedback_max_items,
                semantic_feedback_priority_order=semantic_feedback_priority_order,
                preserve_all_missing_constraint=preserve_all_missing_constraint,
                preserve_all_wrong_objective=preserve_all_wrong_objective,
                preserve_variable_and_constraint_names=preserve_variable_and_constraint_names,
                preserve_one_freeform_instruction=preserve_one_freeform_instruction,
                preserve_error_type_conditioned_feedback=preserve_error_type_conditioned_feedback,
            )
        return build_compressed_repair_feedback_text(
            feedback,
            include_execution_feedback=include_execution_feedback,
            include_static_checks=include_static_checks,
            include_semantic_diagnosis=include_semantic_diagnosis,
            repair_feedback_max_chars=repair_feedback_max_chars,
            repair_feedback_max_items=repair_feedback_max_items,
            semantic_feedback_priority_order=semantic_feedback_priority_order,
        )
    stdout_excerpt = _excerpt(str(feedback.get("stdout", "")))
    stderr_excerpt = _excerpt(str(feedback.get("stderr", "")))
    static_issues = feedback.get("static_issues") or []
    static_findings = feedback.get("static_check_findings") or []
    advisory_diagnosis = feedback.get("advisory_diagnosis") or {}
    diagnosed_errors = advisory_diagnosis.get("diagnosed_errors") if isinstance(advisory_diagnosis, dict) else []
    repair_instructions = advisory_diagnosis.get("repair_instructions") if isinstance(advisory_diagnosis, dict) else []
    reject_reasons = advisory_diagnosis.get("reject_reasons") if isinstance(advisory_diagnosis, dict) else []
    if isinstance(advisory_diagnosis, dict) and advisory_diagnosis.get("parse_success") is False:
        diagnosed_errors = []
        repair_instructions = ["Semantic diagnosis unavailable; use execution feedback."]
        reject_reasons = []
    repair_hint = _runtime_repair_hint(stderr_excerpt)
    lines = ["Repair feedback:"]
    if include_execution_feedback:
        lines.extend(
            [
                "Execution feedback:",
                f"- error_type: {feedback.get('error_type')}",
                f"- compile_error: {feedback.get('compile_error')}",
                f"- compile_error_type: {feedback.get('compile_error_type')}",
                f"- compile_error_line: {feedback.get('compile_error_line')}",
                f"- parsed_objective: {feedback.get('parsed_objective')}",
                f"- stdout_excerpt: {stdout_excerpt}",
                f"- stderr_excerpt: {stderr_excerpt}",
                f"- repair_hint: {repair_hint}",
            ]
        )
    if include_static_checks:
        lines.extend(
            [
                "Static check findings:",
                "- note: Static checks are heuristic warnings, not proof of incorrectness.",
                f"- static_issues: {static_issues}",
                f"- failed_static_checks: {_failed_static_check_names(static_findings)}",
                f"- static_check_findings: {_compact_json(static_findings)}",
            ]
        )
    if include_semantic_diagnosis:
        lines.extend(
            [
                "Semantic diagnosis:",
                f"- semantic_score: {feedback.get('semantic_score')}",
                f"- semantic_should_execute: {feedback.get('semantic_should_execute')}",
                f"- semantic_feedback: {feedback.get('semantic_feedback')}",
                f"- semantic_missing_constraints: {feedback.get('semantic_missing_constraints')}",
                f"- semantic_wrong_objective: {feedback.get('semantic_wrong_objective')}",
                f"- semantic_variable_issues: {feedback.get('semantic_variable_issues')}",
                f"- semantic_gurobi_api_issues: {feedback.get('semantic_gurobi_api_issues')}",
                f"- semantic_output_issues: {feedback.get('semantic_output_issues')}",
                f"- diagnosed_errors: {_compact_json(diagnosed_errors)}",
                f"- repair_instructions: {repair_instructions}",
                f"- reject_reasons: {reject_reasons}",
                f"- semantic_advisory_used: {feedback.get('semantic_advisory_used')}",
            ]
        )
    lines.append("- instruction: Do not repeat the previous code unchanged.")
    if feedback.get("expected_objective") is not None:
        lines.append(f"- expected_objective: {feedback['expected_objective']}")
        lines.append(f"- objective_gap: {feedback.get('objective_gap')}")
    return "\n".join(lines)


def build_compressed_repair_feedback_text(
    feedback: dict,
    *,
    include_execution_feedback: bool = True,
    include_static_checks: bool = True,
    include_semantic_diagnosis: bool = True,
    repair_feedback_max_chars: int | None = None,
    repair_feedback_max_items: int | None = None,
    semantic_feedback_priority_order: list[str] | None = None,
) -> str:
    priority = semantic_feedback_priority_order or [
        "missing_constraint",
        "wrong_objective",
        "domain_issue",
        "output_issue",
        "api_issue",
        "runtime_risk",
        "other",
    ]
    advisory = _preferred_advisory_diagnosis(feedback)
    errors = _prioritized_errors(
        advisory.get("diagnosed_errors") if isinstance(advisory, dict) else [],
        priority=priority,
        max_items=repair_feedback_max_items,
    )
    instructions = _dedupe_preserve_order(
        _stringify_list(advisory.get("repair_instructions") if isinstance(advisory, dict) else [])
    )
    if repair_feedback_max_items is not None:
        instructions = instructions[: max(0, repair_feedback_max_items)]
    static_findings = _unique_static_findings(
        feedback.get("static_check_findings") or [],
        covered_error_types={item.get("type") for item in errors if isinstance(item, dict)},
    )
    lines = ["Repair feedback (compressed):"]
    lines.append(
        "- output_contract: Preserve the harness contract. Return one numeric objective value; do not return dict/list/tuple."
    )
    if include_execution_feedback:
        lines.extend(
            [
                "Execution:",
                f"- error_type: {feedback.get('error_type')}",
                f"- parsed_objective: {feedback.get('parsed_objective')}",
                f"- stdout: {_excerpt(str(feedback.get('stdout', '')), limit=500)}",
                f"- stderr: {_excerpt(str(feedback.get('stderr', '')), limit=500)}",
            ]
        )
    if include_semantic_diagnosis:
        lines.append("Semantic/spec diagnosis:")
        grouped = _group_errors_by_type(errors)
        for error_type in priority + sorted(set(grouped) - set(priority)):
            items = grouped.get(error_type) or []
            if not items:
                continue
            lines.append(f"- {error_type}:")
            for item in items:
                description = str(item.get("description") or "").strip()
                fix = str(item.get("suggested_fix") or "").strip()
                evidence = str(item.get("evidence") or "").strip()
                detail = description
                if fix and fix != description:
                    detail += f" Fix: {fix}"
                if evidence and evidence not in detail:
                    detail += f" Evidence: {_excerpt(evidence, limit=220)}"
                lines.append(f"  - {_excerpt(detail, limit=420)}")
        if instructions:
            lines.append("Repair instructions:")
            for item in instructions:
                lines.append(f"- {_excerpt(item, limit=420)}")
    if include_static_checks and static_findings:
        lines.append("Unique static warnings:")
        for item in static_findings[: repair_feedback_max_items or len(static_findings)]:
            lines.append(
                f"- {item.get('check_name')}: {_excerpt(str(item.get('suggested_fix') or item.get('message') or ''), limit=320)}"
            )
    lines.append("- note: Feedback was compressed; use the problem text as the source of truth.")
    lines.append("- instruction: Do not repeat the previous code unchanged.")
    text = "\n".join(lines)
    if repair_feedback_max_chars is not None and len(text) > repair_feedback_max_chars:
        suffix = "\n- note: Feedback truncated to configured character budget."
        budget = max(0, repair_feedback_max_chars - len(suffix))
        text = text[:budget].rstrip() + suffix
    return text


def build_adaptive_compressed_repair_feedback_text(
    feedback: dict,
    *,
    include_execution_feedback: bool = True,
    include_static_checks: bool = True,
    include_semantic_diagnosis: bool = True,
    repair_feedback_max_chars: int | None = None,
    repair_feedback_max_items: int | None = None,
    semantic_feedback_priority_order: list[str] | None = None,
    preserve_all_missing_constraint: bool = False,
    preserve_all_wrong_objective: bool = False,
    preserve_variable_and_constraint_names: bool = False,
    preserve_one_freeform_instruction: bool = False,
    preserve_error_type_conditioned_feedback: bool = False,
) -> str:
    priority = semantic_feedback_priority_order or [
        "missing_constraint",
        "wrong_objective",
        "domain_issue",
        "output_issue",
        "api_issue",
        "runtime_risk",
        "variable_issue",
        "other",
    ]
    advisory = _preferred_advisory_diagnosis(feedback)
    previous_error_type = str(feedback.get("error_type") or "")
    errors = _adaptive_prioritized_errors(
        advisory.get("diagnosed_errors") if isinstance(advisory, dict) else [],
        priority=priority,
        max_items=repair_feedback_max_items,
        previous_error_type=previous_error_type,
        preserve_all_missing_constraint=preserve_all_missing_constraint,
        preserve_all_wrong_objective=preserve_all_wrong_objective,
        preserve_variable_and_constraint_names=preserve_variable_and_constraint_names,
        preserve_error_type_conditioned_feedback=preserve_error_type_conditioned_feedback,
    )
    instructions = _dedupe_preserve_order(
        _stringify_list(advisory.get("repair_instructions") if isinstance(advisory, dict) else [])
    )
    concrete_instruction = _first_concrete_instruction(instructions) if preserve_one_freeform_instruction else None
    if repair_feedback_max_items is not None:
        instructions = instructions[: max(0, repair_feedback_max_items)]
    static_findings = _unique_static_findings(
        feedback.get("static_check_findings") or [],
        covered_error_types={item.get("type") for item in errors if isinstance(item, dict)},
    )

    lines = ["Repair feedback (adaptive compressed):"]
    lines.append(
        "- output_contract: Preserve the harness contract. Return one numeric objective value; do not return dict/list/tuple."
    )
    if include_execution_feedback:
        lines.extend(
            [
                "Execution:",
                f"- error_type: {feedback.get('error_type')}",
                f"- parsed_objective: {feedback.get('parsed_objective')}",
                f"- stdout: {_excerpt(str(feedback.get('stdout', '')), limit=360)}",
                f"- stderr: {_excerpt(str(feedback.get('stderr', '')), limit=360)}",
            ]
        )
    if include_semantic_diagnosis:
        grouped = _group_errors_by_type(errors)
        if grouped:
            lines.append("Prioritized semantic diagnosis:")
        for error_type in priority + sorted(set(grouped) - set(priority)):
            items = grouped.get(error_type) or []
            if not items:
                continue
            lines.append(f"- {error_type}:")
            for item in items:
                description = str(item.get("description") or "").strip()
                fix = str(item.get("suggested_fix") or "").strip()
                evidence = str(item.get("evidence") or "").strip()
                detail = description
                if fix and fix != description:
                    detail += f" Fix: {fix}"
                if evidence and _has_concrete_model_terms(evidence) and evidence not in detail:
                    detail += f" Evidence: {_excerpt(evidence, limit=160)}"
                lines.append(f"  - {_excerpt(detail, limit=320)}")
        if concrete_instruction:
            lines.append("One concrete repair instruction:")
            lines.append(f"- {_excerpt(concrete_instruction, limit=360)}")
        elif instructions:
            lines.append("Repair instructions:")
            for item in instructions[:1]:
                lines.append(f"- {_excerpt(item, limit=320)}")
    if include_static_checks and static_findings:
        lines.append("Unique static warnings:")
        for item in static_findings[:2]:
            lines.append(
                f"- {item.get('check_name')}: {_excerpt(str(item.get('suggested_fix') or item.get('message') or ''), limit=240)}"
            )
    lines.append("- note: Adaptive compression preserved high-priority semantic items and dropped low-specificity repeats.")
    lines.append("- instruction: Do not repeat the previous code unchanged.")
    return _truncate_feedback("\n".join(lines), repair_feedback_max_chars)


def _repair_spec_context(
    *,
    formulation_spec_text: str | None,
    extracted_spec_text: str | None,
    spec_comparison_text: str | None,
) -> str:
    parts: list[str] = []
    if formulation_spec_text:
        parts.append(
            "Intended formulation spec (advisory, generated from the problem text):\n"
            f"{formulation_spec_text.strip()}"
        )
    if extracted_spec_text:
        parts.append(
            "Previous code extracted formulation spec (advisory):\n"
            f"{extracted_spec_text.strip()}"
        )
    if spec_comparison_text:
        parts.append(
            "Spec-comparison diagnosis (advisory):\n"
            f"{spec_comparison_text.strip()}"
        )
    if not parts:
        return ""
    return "\n\n".join(parts) + "\n\n"


def _compact_static_checks_for_prompt(static_checks: dict | list[dict] | None) -> list[dict]:
    if not static_checks:
        return []
    checks: list[dict] = []
    if isinstance(static_checks, dict):
        raw_checks = static_checks.get("checks", [])
    else:
        raw_checks = static_checks
    if not isinstance(raw_checks, list):
        return []
    for item in raw_checks:
        if not isinstance(item, dict) or item.get("passed") is not False:
            continue
        checks.append(
            {
                "check_name": item.get("check_name"),
                "severity": item.get("severity"),
                "message": item.get("message"),
                "suggested_fix": item.get("suggested_fix"),
            }
        )
    return checks


def render_messages(messages: list[dict]) -> str:
    return json.dumps(messages, indent=2, ensure_ascii=False)


def _repair_task_instruction(error_type: str) -> str:
    if error_type == "compile_failed":
        return (
            "The previous code did not compile. Fix syntax, imports, and function-definition issues first. "
            "Do not focus on objective improvement until the code compiles."
        )
    if error_type == "objective_mismatch":
        return (
            "The previous code executed but returned the wrong objective. Revise the decision variables, "
            "constraints, and objective. Before writing the corrected model logic, include Python comments that restate: "
            "a) decision variables, b) objective direction and expression, and c) every constraint from the problem. "
            "Use any semantic reviewer feedback as advisory evidence, but trust the problem text and execution "
            "feedback most. Then produce corrected executable code only. Verify assignment, coverage, capacity, "
            "and time-overlap logic where relevant."
        )
    if error_type == "runtime_error":
        return (
            "The previous code raised a runtime error. Use the stderr traceback to fix the runtime failure. "
            "Use any semantic reviewer feedback as advisory evidence while preserving executable code."
        )
    if error_type == "semantic_reject":
        return (
            "The semantic checker rejected the previous formulation before solver execution. "
            "Use the semantic feedback to fix missing constraints, variable definitions, objective direction, "
            "Gurobi API issues, and objective-return behavior before trying again."
        )
    return "The previous optimization code failed before producing the expected result. Fix the code."


def _execution_output_contract() -> str:
    return (
        "Mandatory execution/output contract:\n"
        "- create a Gurobi model\n"
        "- add variables and constraints\n"
        "- call model.setObjective(...)\n"
        "- call model.optimize()\n"
        "- if optimal, return a single numeric objective value (float/int) or print OBJECTIVE=<number>\n"
        "- do not return a dict/list/tuple as the objective result\n"
        "- do not omit objective output even when fixing formulation errors"
    )


def _excerpt(text: str, limit: int = 2000) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


def _runtime_repair_hint(stderr_excerpt: str) -> str | None:
    lowered = stderr_excerpt.lower()
    if (
        "missing constraint index" in lowered
        or "tuple' object has no attribute 'gi_frame" in lowered
        or "tuple object has no attribute gi_frame" in lowered
        or "model.addconstrs" in lowered
    ):
        return (
            "For a single constraint, use model.addConstr(expr <= rhs, name='...'). "
            "Use model.addConstrs only with a generator over an index set. "
            "Never pass (constraint_expr, 'name') into addConstrs."
        )
    return None


def _compact_json(value: object, limit: int = 1200) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False)
    except TypeError:
        text = str(value)
    return _excerpt(text, limit=limit)


def _failed_static_check_names(static_findings: object) -> list[str]:
    if not isinstance(static_findings, list):
        return []
    names: list[str] = []
    for item in static_findings:
        if not isinstance(item, dict):
            continue
        if item.get("passed") is False:
            names.append(str(item.get("check_name") or "unknown"))
    return names


def _preferred_advisory_diagnosis(feedback: dict) -> dict:
    spec_payload = feedback.get("spec_comparison_result") or feedback.get("spec_comparison")
    if isinstance(spec_payload, dict):
        diagnosis = spec_payload.get("advisory_diagnosis")
        if isinstance(diagnosis, dict):
            return diagnosis
    diagnosis = feedback.get("advisory_diagnosis")
    return diagnosis if isinstance(diagnosis, dict) else {}


def _prioritized_errors(
    value: object,
    *,
    priority: list[str],
    max_items: int | None,
) -> list[dict]:
    if not isinstance(value, list):
        return []
    deduped: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        key = (str(item.get("type") or "other"), str(item.get("description") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    order = {name: index for index, name in enumerate(priority)}
    deduped.sort(key=lambda item: (order.get(str(item.get("type") or "other"), 10_000), str(item.get("description") or "")))
    if max_items is not None:
        return deduped[: max(0, max_items)]
    return deduped


def _adaptive_prioritized_errors(
    value: object,
    *,
    priority: list[str],
    max_items: int | None,
    previous_error_type: str,
    preserve_all_missing_constraint: bool,
    preserve_all_wrong_objective: bool,
    preserve_variable_and_constraint_names: bool,
    preserve_error_type_conditioned_feedback: bool,
) -> list[dict]:
    if not isinstance(value, list):
        return []
    all_errors = _prioritized_errors(value, priority=priority, max_items=None)
    selected: list[dict] = []
    selected_keys: set[tuple[str, str, str]] = set()

    def add(item: dict) -> None:
        key = (
            str(item.get("type") or "other"),
            str(item.get("description") or ""),
            str(item.get("suggested_fix") or ""),
        )
        if key in selected_keys:
            return
        selected_keys.add(key)
        selected.append(item)

    for item in all_errors:
        error_type = str(item.get("type") or "other")
        if error_type == "missing_constraint" and preserve_all_missing_constraint:
            add(item)
        elif error_type == "wrong_objective" and preserve_all_wrong_objective:
            add(item)

    lower_error = previous_error_type.lower()
    for item in all_errors:
        error_type = str(item.get("type") or "other")
        if error_type in {"variable_issue", "domain_issue"} and preserve_variable_and_constraint_names:
            if _has_concrete_model_terms(_diagnosis_item_text(item)):
                add(item)
        elif preserve_error_type_conditioned_feedback and error_type == "output_issue":
            if lower_error in {"no_objective", "output_issue"}:
                add(item)
        elif preserve_error_type_conditioned_feedback and error_type in {"runtime_risk", "api_issue", "compile_risk"}:
            if lower_error in {"runtime_error", "compile_failed"}:
                add(item)

    target = max_items if max_items is not None else len(all_errors)
    remaining_slots = max(0, target - len(selected))
    has_specific_candidates = any(str(item.get("type") or "other") != "other" for item in all_errors)
    for item in all_errors:
        if remaining_slots <= 0:
            break
        error_type = str(item.get("type") or "other")
        if error_type == "other" and has_specific_candidates:
            continue
        before = len(selected)
        add(item)
        if len(selected) > before:
            remaining_slots -= 1

    return selected


def _diagnosis_item_text(item: dict) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in ("type", "description", "evidence", "suggested_fix")
    )


def _has_concrete_model_terms(text: str) -> bool:
    lowered = text.lower()
    if re.search(r"[a-zA-Z_][a-zA-Z0-9_]*\[[^\]]+\]", text):
        return True
    if re.search(r"`[^`]{2,}`|'[^']{2,}'|\"[^\"]{2,}\"", text):
        return True
    concrete_terms = {
        "variable",
        "constraint",
        "capacity",
        "demand",
        "supply",
        "inventory",
        "flow",
        "balance",
        "route",
        "raw",
        "labor",
        "product",
        "premium",
        "expansion",
        "year",
        "machine",
        "facility",
        "material",
        "assignment",
        "binary",
        "integer",
        "bound",
        "objective",
    }
    return any(term in lowered for term in concrete_terms)


def _first_concrete_instruction(instructions: list[str]) -> str | None:
    for item in instructions:
        if _has_concrete_model_terms(item):
            return item
    return instructions[0] if instructions else None


def _truncate_feedback(text: str, max_chars: int | None) -> str:
    if max_chars is None or len(text) <= max_chars:
        return text
    suffix = "\n- note: Feedback truncated to configured character budget."
    budget = max(0, max_chars - len(suffix))
    return text[:budget].rstrip() + suffix


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = value.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _stringify_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _group_errors_by_type(errors: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for item in errors:
        grouped.setdefault(str(item.get("type") or "other"), []).append(item)
    return grouped


def _unique_static_findings(static_findings: object, *, covered_error_types: set[object]) -> list[dict]:
    if not isinstance(static_findings, list):
        return []
    covered = {str(item) for item in covered_error_types}
    suppress_by_type = {
        "missing_constraint": {"constraints_created", "variables_created_but_no_constraints", "all_constraints_same_direction_warning"},
        "wrong_objective": {"calls_set_objective", "no_objective_found", "suspicious_constant_only_objective"},
        "output_issue": {"has_objective_output_or_print", "missing_expected_objective_print_format", "no_objective_output_found"},
        "api_issue": {"common_addConstrs_misuse"},
        "runtime_risk": {"python_parseable_with_ast"},
    }
    suppressed_checks: set[str] = set()
    for error_type in covered:
        suppressed_checks.update(suppress_by_type.get(error_type, set()))
    result: list[dict] = []
    seen: set[str] = set()
    for item in static_findings:
        if not isinstance(item, dict) or item.get("passed") is not False:
            continue
        name = str(item.get("check_name") or "")
        if name in suppressed_checks or name in seen:
            continue
        seen.add(name)
        result.append(item)
    return result
