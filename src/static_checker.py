"""Permissive static checks for extracted optimization code."""

from __future__ import annotations

import ast
import re
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class StaticCheckFinding:
    check_name: str
    passed: bool
    severity: str
    message: str
    suggested_fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class StaticCheckResult:
    passed: bool
    issues: list[str] = field(default_factory=list)
    signals: dict[str, bool] = field(default_factory=dict)
    compile_error: str | None = None
    compile_error_line: int | None = None
    compile_error_type: str | None = None
    checks: list[dict[str, Any]] = field(default_factory=list)


def check_code(code: str, problem_text: str = "") -> StaticCheckResult:
    stripped = code.strip()
    signals: dict[str, bool] = {
        "empty_code": not bool(stripped),
        "python_compile_ok": False,
        "has_gurobi_import_or_usage": False,
        "has_model_creation": False,
        "has_variable_hint": False,
        "has_constraint_hint": False,
        "has_objective_hint": False,
        "has_optimize_hint": False,
        "has_output_hint": False,
        "has_numeric_objective_output_contract": False,
        "has_function_def": False,
    }
    issues: list[str] = []
    checks: list[StaticCheckFinding] = []
    compile_error: str | None = None
    compile_error_line: int | None = None
    compile_error_type: str | None = None

    if not stripped:
        issues.append("empty_code")
        _add_check(
            checks,
            "non_empty_code",
            False,
            "error",
            "No extracted Python code was found.",
            "Return one executable Python code block defining solve() or solve_model().",
        )
        return StaticCheckResult(
            passed=False,
            issues=issues,
            signals=signals,
            compile_error=compile_error,
            compile_error_line=compile_error_line,
            compile_error_type=compile_error_type,
            checks=[item.to_dict() for item in checks],
        )

    tree: ast.AST | None = None
    try:
        compile(code, "<extracted_code>", "exec")
        signals["python_compile_ok"] = True
        tree = ast.parse(code)
        _add_check(checks, "python_parseable_with_ast", True, "info", "Code parses as Python.")
    except SyntaxError as exc:
        compile_error = f"{exc.__class__.__name__}: {exc.msg}"
        compile_error_line = exc.lineno
        compile_error_type = exc.__class__.__name__
        issues.append("python_compile_failed")
        _add_check(
            checks,
            "python_parseable_with_ast",
            False,
            "error",
            f"Code is not parseable Python: {compile_error}.",
            "Fix syntax errors before changing the formulation.",
        )

    _add_check(checks, "non_empty_code", True, "info", "Extracted code is non-empty.")

    signals["has_gurobi_import_or_usage"] = bool(
        re.search(r"\bimport\s+gurobipy\b|\bfrom\s+gurobipy\s+import\b|\bgurobipy\.|\bgp\.", code)
    )
    signals["has_model_creation"] = _has_model_creation(code)
    signals["has_variable_hint"] = bool(re.search(r"\baddVars?\s*\(", code))
    signals["has_constraint_hint"] = bool(re.search(r"\baddConstrs?\s*\(", code))
    signals["has_objective_hint"] = bool(re.search(r"\bsetObjective\s*\(", code))
    signals["has_optimize_hint"] = bool(re.search(r"\boptimize\s*\(", code))
    signals["has_output_hint"] = bool(
        re.search(r"\bprint\s*\(|\breturn\b|\bwrite\s*\(|\bsave\w*\s*\(", code)
    )
    signals["has_numeric_objective_output_contract"] = _has_numeric_objective_output_contract(code, tree)
    signals["has_function_def"] = bool(re.search(r"(?m)^\s*def\s+\w+\s*\(", code))

    for name, present in signals.items():
        if name in {"empty_code", "python_compile_ok"}:
            continue
        if not present:
            issues.append(f"missing_{name}")

    _add_signal_check(
        checks,
        "uses_gurobi_or_gurobipy",
        signals["has_gurobi_import_or_usage"],
        "warning",
        "Code does not appear to import or use gurobipy.",
        "Use gurobipy/gp to build the optimization model.",
    )
    _add_signal_check(
        checks,
        "creates_model",
        signals["has_model_creation"],
        "warning",
        "Code does not appear to create a Gurobi model.",
        "Create a gp.Model()/Model() instance.",
    )
    _add_signal_check(
        checks,
        "variables_created",
        signals["has_variable_hint"],
        "warning",
        "No decision variables were detected.",
        "Create decision variables with addVar or addVars.",
    )
    _add_signal_check(
        checks,
        "constraints_created",
        signals["has_constraint_hint"],
        "warning",
        "No model constraints were detected.",
        "Translate every natural-language restriction into addConstr/addConstrs calls.",
    )
    _add_signal_check(
        checks,
        "calls_set_objective",
        signals["has_objective_hint"],
        "warning",
        "No setObjective call was detected.",
        "Set the model objective with model.setObjective(...).",
    )
    _add_signal_check(
        checks,
        "calls_optimize",
        signals["has_optimize_hint"],
        "warning",
        "No optimize() call was detected.",
        "Call model.optimize() before reading the objective.",
    )
    _add_signal_check(
        checks,
        "has_objective_output_or_print",
        signals["has_output_hint"],
        "warning",
        "Code does not appear to return or print an objective value.",
        "Return a single numeric objective value from solve()/solve_model(), or print OBJECTIVE=<number>.",
    )
    _add_signal_check(
        checks,
        "numeric_objective_output_contract",
        signals["has_numeric_objective_output_contract"],
        "warning",
        "The harness may not parse the objective because the function appears to return a container or non-numeric result.",
        "Your previous code did not expose a numeric objective value. Add model.setObjective, model.optimize, and return model.ObjVal as a float/int or print OBJECTIVE=<number>. Do not return a dict/list/tuple.",
    )
    _add_signal_check(
        checks,
        "no_objective_found",
        signals["has_objective_hint"],
        "warning",
        "The model objective is missing.",
        "Add model.setObjective(expression, GRB.MINIMIZE/MAXIMIZE).",
    )
    _add_signal_check(
        checks,
        "no_objective_output_found",
        signals["has_output_hint"],
        "warning",
        "The objective value may not be exposed to the harness.",
        "Return only the optimized numeric objective value from solve()/solve_model(), not a dict/list/tuple.",
    )
    _add_check(
        checks,
        "missing_expected_objective_print_format",
        bool(re.search(r"OBJECTIVE\s*=", code)) or signals["has_output_hint"],
        "info",
        "The code does not explicitly print OBJECTIVE=..., but returning the objective is acceptable for this harness.",
        "Return model.ObjVal, or print OBJECTIVE=<value> if writing standalone scripts.",
    )
    _add_check(
        checks,
        "variables_created_but_no_constraints",
        not (signals["has_variable_hint"] and not signals["has_constraint_hint"]),
        "warning",
        "Decision variables are created but no constraints are detected.",
        "Add the structural constraints from the problem statement.",
    )
    _add_check(
        checks,
        "common_addConstrs_misuse",
        not _has_addconstrs_misuse_pattern(code),
        "error",
        "Likely addConstrs misuse: passing a named tuple-like pair instead of a generator expression.",
        "Use addConstr for one constraint or addConstrs(generator, name='...') for indexed constraints.",
    )
    _add_check(
        checks,
        "multiplication_of_decision_variables_without_quadratic_handling",
        not _has_obvious_decision_var_product(tree) if tree is not None else True,
        "warning",
        "The objective or constraints appear to multiply decision variables.",
        "Linearize the product, or explicitly configure a quadratic model when appropriate.",
    )
    _add_check(
        checks,
        "suspicious_constant_only_objective",
        not _has_constant_only_objective(tree) if tree is not None else True,
        "warning",
        "The objective appears to be constant and may ignore decision variables.",
        "Build the objective from decision variables and coefficients.",
    )
    _add_check(
        checks,
        "objective_variables_not_in_constraints",
        not _objective_variables_not_in_constraints(code, tree),
        "warning",
        "Some objective variables do not appear in constraints.",
        "Check that objective variables are linked to feasibility constraints.",
    )
    _add_check(
        checks,
        "all_constraints_same_direction_warning",
        not _all_constraints_same_direction(code),
        "warning",
        "All detected constraints use the same inequality direction.",
        "Check whether equality, balance, lower-bound, or demand constraints are missing.",
    )
    _add_check(
        checks,
        "likely_flow_problem_without_equalities",
        not _likely_flow_problem_without_equalities(problem_text, code),
        "warning",
        "Problem text suggests flow/balance/conservation, but no equality constraints were detected.",
        "Add flow-balance, inventory-conservation, or supply-demand equality constraints where required.",
    )

    return StaticCheckResult(
        passed=bool(stripped) and signals["python_compile_ok"],
        issues=issues,
        signals=signals,
        compile_error=compile_error,
        compile_error_line=compile_error_line,
        compile_error_type=compile_error_type,
        checks=[item.to_dict() for item in checks],
    )


def run_static_checks(code: str, problem_text: str = "") -> StaticCheckResult:
    return check_code(code, problem_text=problem_text)


def _has_model_creation(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return bool(re.search(r"\bgp\.Model\s*\(|\bgurobipy\.Model\s*\(|\bModel\s*\(", code))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _is_model_constructor(node.func):
            return True
    return False


def _is_model_constructor(func: ast.AST) -> bool:
    if isinstance(func, ast.Name):
        return func.id == "Model"
    if isinstance(func, ast.Attribute) and func.attr == "Model":
        value = func.value
        return isinstance(value, ast.Name) and value.id in {"gp", "gurobipy"}
    return False


def _has_numeric_objective_output_contract(code: str, tree: ast.AST | None) -> bool:
    if re.search(r"OBJECTIVE\s*=", code):
        return True
    if tree is None:
        return bool(
            re.search(
                r"return\s+(?:float\s*\(|(?:model|m)\.(?:ObjVal|objVal)|[A-Za-z_]\w*\.ObjVal|[A-Za-z_]\w*\.objVal)",
                code,
            )
        )
    saw_non_none_return = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Return):
            continue
        value = node.value
        if value is None:
            continue
        if isinstance(value, ast.Constant) and value.value is None:
            continue
        if isinstance(value, (ast.Dict, ast.List, ast.Tuple, ast.Set)):
            return False
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id in {"dict", "list", "tuple", "set"}:
            return False
        saw_non_none_return = True
    return saw_non_none_return


def _add_signal_check(
    checks: list[StaticCheckFinding],
    check_name: str,
    passed: bool,
    severity: str,
    message: str,
    suggested_fix: str,
) -> None:
    _add_check(
        checks,
        check_name,
        passed,
        "info" if passed else severity,
        "OK." if passed else message,
        "" if passed else suggested_fix,
    )


def _add_check(
    checks: list[StaticCheckFinding],
    check_name: str,
    passed: bool,
    severity: str,
    message: str,
    suggested_fix: str = "",
) -> None:
    checks.append(
        StaticCheckFinding(
            check_name=check_name,
            passed=passed,
            severity=severity,
            message=message,
            suggested_fix=suggested_fix,
        )
    )


def _has_addconstrs_misuse_pattern(code: str) -> bool:
    patterns = (
        r"\.addConstrs\s*\([^)]*,\s*['\"]",
        r"\.addConstrs\s*\(\s*\([^)]*,\s*['\"]",
    )
    return any(re.search(pattern, code, flags=re.DOTALL) for pattern in patterns)


def _has_obvious_decision_var_product(tree: ast.AST | None) -> bool:
    if tree is None:
        return False
    decision_var_roots = _decision_variable_roots(tree)
    if not decision_var_roots:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Mult):
            continue
        if _references_decision_var(node.left, decision_var_roots) and _references_decision_var(
            node.right,
            decision_var_roots,
        ):
            return True
    return False


def _decision_variable_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Call) or not isinstance(node.value.func, ast.Attribute):
            continue
        if node.value.func.attr not in {"addVar", "addVars"}:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                roots.add(target.id)
    return roots


def _references_decision_var(node: ast.AST, roots: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in roots
    if isinstance(node, ast.Subscript):
        return _references_decision_var(node.value, roots)
    if isinstance(node, ast.Attribute):
        return _references_decision_var(node.value, roots)
    return any(_references_decision_var(child, roots) for child in ast.iter_child_nodes(node))


def _has_constant_only_objective(tree: ast.AST | None) -> bool:
    if tree is None:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "setObjective" or not node.args:
            continue
        expression = node.args[0]
        return not any(isinstance(child, (ast.Name, ast.Subscript, ast.Attribute)) for child in ast.walk(expression))
    return False


def _objective_variables_not_in_constraints(code: str, tree: ast.AST | None) -> bool:
    if tree is None:
        return False
    objective_text = ""
    constraint_text = ""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "setObjective" and node.args:
            objective_text += ast.get_source_segment(code, node.args[0]) or ""
        if node.func.attr in {"addConstr", "addConstrs"}:
            constraint_text += ast.get_source_segment(code, node) or ""
    objective_names = set(re.findall(r"\b[A-Za-z_]\w*\b", objective_text))
    constraint_names = set(re.findall(r"\b[A-Za-z_]\w*\b", constraint_text))
    ignored = {"gp", "GRB", "quicksum", "sum", "range", "len", "MINIMIZE", "MAXIMIZE"}
    objective_names -= ignored
    return bool(objective_names) and not bool(objective_names & constraint_names)


def _all_constraints_same_direction(code: str) -> bool:
    constraint_lines = [
        line
        for line in code.splitlines()
        if "addConstr" in line or "addConstrs" in line
    ]
    if len(constraint_lines) < 2:
        return False
    directions: set[str] = set()
    for line in constraint_lines:
        if "==" in line or "GRB.EQUAL" in line:
            directions.add("==")
        elif ">=" in line or "GRB.GREATER_EQUAL" in line:
            directions.add(">=")
        elif "<=" in line or "GRB.LESS_EQUAL" in line:
            directions.add("<=")
    return len(directions) == 1 and "==" not in directions


def _likely_flow_problem_without_equalities(problem_text: str, code: str) -> bool:
    if not problem_text:
        return False
    text = problem_text.lower()
    flow_terms = (
        "flow",
        "convert",
        "route",
        "balance",
        "inventory",
        "conservation",
        "demand",
        "supply",
    )
    if not any(term in text for term in flow_terms):
        return False
    return "==" not in code and "GRB.EQUAL" not in code
