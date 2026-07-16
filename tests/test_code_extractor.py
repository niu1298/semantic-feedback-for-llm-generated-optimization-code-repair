from __future__ import annotations

import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from src.code_extractor import extract_code


def test_code_extractor_extracts_python_fenced_block() -> None:
    response = """
Here is the code:

```python
print("short")
```

```python
import gurobipy as gp
model = gp.Model()
model.optimize()
```
"""

    result = extract_code(response)

    assert result["had_code_fence"]
    assert result["language"] == "python"
    assert "import gurobipy" in result["code"]
    assert result["warning"] == "multiple_python_fences_longest_selected"


def test_code_extractor_handles_complete_python_fence() -> None:
    response = """
Ignore this prose.
```python
def solve():
    return 1
```
"""

    result = extract_code(response)

    assert result["had_code_fence"]
    assert result["language"] == "python"
    assert result["code"] == "def solve():\n    return 1"
    assert result["warning"] is None


def test_code_extractor_handles_unterminated_python_fence() -> None:
    response = """
Here is code:
```python
def solve():
    return 1
"""

    result = extract_code(response)

    assert result["had_code_fence"]
    assert result["language"] == "python"
    assert result["code"] == "def solve():\n    return 1"
    assert result["warning"] == "unterminated_python_fence"


def test_code_extractor_does_not_include_prose_before_fence() -> None:
    response = """This is an explanation that should not be extracted.

```python
print("only code")
```
"""

    result = extract_code(response)

    assert "explanation" not in result["code"]
    assert result["code"] == 'print("only code")'


def test_code_extractor_handles_no_fence() -> None:
    result = extract_code("print('ok')")

    assert not result["had_code_fence"]
    assert result["language"] is None
    assert result["code"] == "print('ok')"
    assert result["warning"] == "no_code_fence_found"
