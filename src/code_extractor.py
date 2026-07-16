"""Extract Python code from raw LLM responses."""

from __future__ import annotations

import re
from typing import Any


_FENCE_START_RE = re.compile(r"```(?P<language>[A-Za-z0-9_+.-]*)[ \t]*(?:\r?\n|$)")


def extract_code(response_text: str) -> dict[str, Any]:
    """Extract likely Python code from a model response.

    Preference order:
    1. Longest fenced block tagged `python` or `py`, including unterminated blocks.
    2. Longest generic fenced block, including unterminated blocks.
    3. Whole response when no fence exists.
    """

    fences = _find_fences(response_text)
    python_fences = [
        fence
        for fence in fences
        if (fence["language"] or "").lower() in {"python", "py"}
    ]
    if python_fences:
        selected = _longest_code_block(python_fences)
        warning = _warning_for_python_fence(selected, len(python_fences))
        return _result_from_fence(selected, warning)

    if fences:
        selected = _longest_code_block(fences)
        warning = _warning_for_generic_fence(selected)
        return _result_from_fence(selected, warning)

    return {
        "code": response_text.strip(),
        "had_code_fence": False,
        "language": None,
        "warning": "no_code_fence_found",
    }


def _find_fences(text: str) -> list[dict[str, Any]]:
    fences: list[dict[str, Any]] = []
    pos = 0
    while True:
        match = _FENCE_START_RE.search(text, pos)
        if match is None:
            break

        content_start = match.end()
        language = (match.group("language") or "").strip() or None
        closing_start = text.find("```", content_start)
        if closing_start == -1:
            code = text[content_start:]
            terminated = False
            pos = len(text)
        else:
            code = text[content_start:closing_start]
            terminated = True
            pos = closing_start + 3

        fences.append(
            {
                "code": code.strip(),
                "language": language,
                "terminated": terminated,
            }
        )
    return fences


def _result_from_fence(fence: dict[str, Any], warning: str | None) -> dict[str, Any]:
    return {
        "code": str(fence["code"]).strip(),
        "had_code_fence": True,
        "language": fence["language"],
        "warning": warning,
    }


def _warning_for_python_fence(fence: dict[str, Any], count: int) -> str | None:
    if not fence["terminated"]:
        return "unterminated_python_fence"
    if count > 1:
        return "multiple_python_fences_longest_selected"
    return None


def _warning_for_generic_fence(fence: dict[str, Any]) -> str:
    if not fence["terminated"]:
        return "unterminated_fence"
    if fence["language"] is None:
        return "generic_fence_used"
    return f"non_python_fence_used:{fence['language']}"


def _longest_code_block(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    return max(blocks, key=lambda block: len(str(block["code"])))
