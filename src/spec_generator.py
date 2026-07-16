"""Problem-statement to intended formulation-spec generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .formulation_spec import FormulationSpecResult, parse_formulation_spec_response


@dataclass(frozen=True, slots=True)
class SpecGenerationCall:
    messages: list[dict[str, str]]
    max_tokens: int | None = None
    model: str | None = None
    provider: str | None = None


def build_intended_spec_prompt(
    problem_statement: str,
    *,
    problem_id: str,
    prompt_style: str = "full",
) -> list[dict[str, str]]:
    schema = _spec_schema_text()
    if prompt_style == "compact":
        user = (
            f"Problem id: {problem_id}\n"
            "Extract the intended optimization formulation from the problem text. "
            "Do not solve numerically. Return JSON only.\n\n"
            f"Problem:\n{problem_statement.strip()}\n\n"
            f"Schema:\n{schema}"
        )
    elif prompt_style == "full":
        user = (
            f"Problem id: {problem_id}\n\n"
            "Describe the intended mathematical optimization formulation, not Python code. "
            "Include decision variables, domains/integrality, objective direction and terms, "
            "constraints with senses, and output requirements. Do not solve the problem numerically. "
            "Do not mention or infer any expected objective value. Return strict JSON only.\n\n"
            f"Problem statement:\n{problem_statement.strip()}\n\n"
            f"JSON schema:\n{schema}"
        )
    else:
        raise ValueError("spec_prompt_style must be one of: full, compact")
    return [
        {
            "role": "system",
            "content": (
                "You write compact optimization formulation specifications as strict JSON. "
                "No markdown, prose, comments, or code fences."
            ),
        },
        {"role": "user", "content": user},
    ]


def generate_intended_formulation_spec(
    problem_statement: str,
    problem_id: str,
    config: Any,
    llm_client: Any,
) -> FormulationSpecResult:
    messages = build_intended_spec_prompt(
        problem_statement,
        problem_id=problem_id,
        prompt_style=str(getattr(config, "spec_prompt_style", "full") or "full"),
    )
    raw = _chat(llm_client, messages)
    return parse_formulation_spec_response(raw, problem_id=problem_id, source="intended")


def _chat(client: Any, messages: list[dict[str, str]]) -> str:
    if hasattr(client, "chat_with_metadata"):
        payload = client.chat_with_metadata(messages)
        return str(payload.get("text", ""))
    return str(client.chat(messages))


def _spec_schema_text() -> str:
    return json.dumps(
        {
            "problem_id": "string",
            "source": "intended",
            "problem_type": "LP | ILP | MILP | NLP | unknown",
            "sense": "minimize | maximize | unknown",
            "decision_variables": [
                {
                    "name": "string",
                    "meaning": "string",
                    "indexing": "string",
                    "domain": "continuous | integer | binary | nonnegative continuous | nonnegative integer | unknown",
                }
            ],
            "objective": {
                "direction": "minimize | maximize | unknown",
                "terms": [
                    {
                        "description": "string",
                        "coefficient_or_formula": "string",
                        "variables_involved": ["string"],
                    }
                ],
            },
            "constraints": [
                {
                    "name": "string",
                    "description": "string",
                    "mathematical_form": "string",
                    "sense": "<= | >= | == | unknown | other",
                    "variables_involved": ["string"],
                }
            ],
            "output_requirements": ["string"],
            "notes": "string",
        },
        ensure_ascii=False,
    )
