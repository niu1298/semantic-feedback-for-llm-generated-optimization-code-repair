"""Generated-code to formulation-spec extraction."""

from __future__ import annotations

import json
from typing import Any

from .formulation_spec import FormulationSpecResult, parse_formulation_spec_response


def build_code_spec_prompt(
    problem_statement: str,
    generated_code: str,
    *,
    problem_id: str,
    prompt_style: str = "full",
) -> list[dict[str, str]]:
    schema = json.dumps(
        {
            "problem_id": problem_id,
            "source": "extracted",
            "problem_type": "LP | ILP | MILP | NLP | unknown",
            "sense": "minimize | maximize | unknown",
            "decision_variables": [],
            "objective": {
                "direction": "unknown",
                "terms": [
                    {
                        "description": "string",
                        "coefficient_or_formula": "string, e.g. '2.00 * 150'",
                        "variables_involved": ["string"],
                    }
                ],
            },
            "constraints": [
                {
                    "name": "string",
                    "description": "string",
                    "mathematical_form": "string, e.g. 'x1 + x2 == 1000'",
                    "sense": "<= | >= | == | unknown | other",
                    "variables_involved": ["string"],
                }
            ],
            "output_requirements": [],
            "notes": "string",
        },
        ensure_ascii=False,
    )
    if prompt_style == "compact":
        instruction = (
            "Describe what the code actually models. Mark missing objective/output/constraints explicitly. "
            "Return valid JSON: arithmetic formulas must be strings."
        )
    elif prompt_style == "full":
        instruction = (
            "Read the generated Python/Gurobi code and describe what the code actually models, "
            "not what the original problem intended. Identify variables, objective direction/terms, "
            "constraints, domains, and output behavior. If objective, output, or constraints are missing, "
            "explicitly mark them as missing. Return strict JSON only. Arithmetic formulas must be strings."
        )
    else:
        raise ValueError("code_spec_prompt_style must be one of: full, compact")
    return [
        {
            "role": "system",
            "content": "You extract optimization formulation specs from code as strict JSON only.",
        },
        {
            "role": "user",
            "content": (
                f"Problem id: {problem_id}\n"
                f"{instruction}\n\n"
                f"Original problem statement for context:\n{problem_statement.strip()}\n\n"
                f"Generated code:\n```python\n{generated_code.strip()}\n```\n\n"
                "JSON validity rules:\n"
                "- Return one JSON object only; no markdown or prose.\n"
                "- Do not put arithmetic expressions directly as JSON values.\n"
                "- Invalid: {\"coefficient\": 2.00 * 150}\n"
                "- Valid: {\"coefficient_or_formula\": \"2.00 * 150\"}\n"
                "- Put mathematical forms such as x1 + x2 == 1000 inside strings.\n\n"
                f"Schema example:\n{schema}"
            ),
        },
    ]


def extract_code_formulation_spec(
    problem_statement: str,
    generated_code: str,
    problem_id: str,
    config: Any,
    llm_client: Any,
) -> FormulationSpecResult:
    if not generated_code.strip():
        return parse_formulation_spec_response("", problem_id=problem_id, source="extracted")
    messages = build_code_spec_prompt(
        problem_statement,
        generated_code,
        problem_id=problem_id,
        prompt_style=str(getattr(config, "code_spec_prompt_style", "full") or "full"),
    )
    raw = _chat(llm_client, messages)
    return parse_formulation_spec_response(raw, problem_id=problem_id, source="extracted")


def _chat(client: Any, messages: list[dict[str, str]]) -> str:
    if hasattr(client, "chat_with_metadata"):
        payload = client.chat_with_metadata(messages)
        return str(payload.get("text", ""))
    return str(client.chat(messages))
