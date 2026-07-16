"""Parse objective values from execution stdout."""

from __future__ import annotations

import re


_NUMBER_RE = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_OBJECTIVE_RE = re.compile(rf"OBJECTIVE\s*=\s*({_NUMBER_RE})")


def parse_objective(stdout: str, returncode: int = 0) -> float | None:
    del returncode
    explicit = _OBJECTIVE_RE.search(stdout)
    if explicit:
        return float(explicit.group(1))
    return None
