from __future__ import annotations

import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from src.static_checker import check_code


def test_static_checker_catches_empty_code() -> None:
    result = check_code("")

    assert not result.passed
    assert "empty_code" in result.issues


def test_static_checker_compiles_valid_python() -> None:
    code = """
import gurobipy as gp

def solve():
    model = gp.Model("demo")
    x = model.addVar(name="x")
    model.setObjective(x)
    model.addConstr(x >= 0)
    model.optimize()
    return model.ObjVal
"""

    result = check_code(code)

    assert result.passed
    assert result.signals["python_compile_ok"]
    assert result.signals["has_function_def"]


def test_static_checker_catches_syntax_error() -> None:
    result = check_code("def broken(:\n    pass")

    assert not result.passed
    assert "python_compile_failed" in result.issues
    assert not result.signals["python_compile_ok"]
    assert result.compile_error is not None
    assert result.compile_error_type == "SyntaxError"
    assert result.compile_error_line == 1


def test_static_checker_detects_gurobipy_model_signals() -> None:
    code = """
import gurobipy as gp

def solve():
    model = gp.Model("demo")
    x = model.addVars(2, name="x")
    model.addConstrs(x[i] >= 0 for i in range(2))
    model.setObjective(x[0] + x[1])
    model.optimize()
    return model.ObjVal
"""

    result = check_code(code)

    assert result.passed
    assert result.signals["has_gurobi_import_or_usage"]
    assert result.signals["has_model_creation"]
    assert result.signals["has_variable_hint"]
    assert result.signals["has_constraint_hint"]
    assert result.signals["has_objective_hint"]
    assert result.signals["has_optimize_hint"]
    assert result.signals["has_output_hint"]
    assert result.signals["has_function_def"]


def test_static_checker_ast_detects_model_creation() -> None:
    code = """
from gurobipy import Model

def solve_model():
    model = Model("demo")
    return None
"""

    result = check_code(code)

    assert result.passed
    assert result.signals["has_model_creation"]


def test_static_checker_detects_function_def() -> None:
    result = check_code("def solve_model():\n    return None\n")

    assert result.passed
    assert result.signals["has_function_def"]
    assert "missing_has_function_def" not in result.issues


def test_static_checker_reports_missing_set_objective() -> None:
    result = check_code("import gurobipy as gp\ndef solve_model():\n    m = gp.Model()\n    return None\n")

    failed = {item["check_name"] for item in result.checks if item["passed"] is False}

    assert "calls_set_objective" in failed
    assert "no_objective_found" in failed


def test_static_checker_reports_missing_optimize() -> None:
    result = check_code(
        "import gurobipy as gp\n"
        "def solve_model():\n"
        "    m = gp.Model()\n"
        "    x = m.addVar()\n"
        "    m.setObjective(x)\n"
        "    return 0\n"
    )

    failed = {item["check_name"] for item in result.checks if item["passed"] is False}

    assert "calls_optimize" in failed


def test_static_checker_reports_missing_objective_output() -> None:
    result = check_code(
        "import gurobipy as gp\n"
        "def solve_model():\n"
        "    m = gp.Model()\n"
        "    x = m.addVar()\n"
        "    m.setObjective(x)\n"
        "    m.optimize()\n"
    )

    failed = {item["check_name"] for item in result.checks if item["passed"] is False}

    assert "has_objective_output_or_print" in failed
    assert "no_objective_output_found" in failed


def test_static_checker_flow_problem_without_equalities_warning() -> None:
    result = check_code(
        "import gurobipy as gp\n"
        "def solve_model():\n"
        "    m = gp.Model()\n"
        "    x = m.addVar()\n"
        "    m.addConstr(x <= 5)\n"
        "    m.setObjective(x)\n"
        "    m.optimize()\n"
        "    return m.ObjVal\n",
        problem_text="Route flow with supply demand balance.",
    )

    failed = {item["check_name"] for item in result.checks if item["passed"] is False}

    assert "likely_flow_problem_without_equalities" in failed
