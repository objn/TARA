from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Dict

from core.services.agents.main import Tool


JsonDict = Dict[str, Any]


class CalculatorError(ValueError):
    pass


@dataclass(frozen=True)
class _EvalConfig:
    max_nodes: int = 10_000


def _eval_expr(expr: str, *, cfg: _EvalConfig = _EvalConfig()) -> float:
    """
    Safely evaluate a basic arithmetic expression.

    Supported:
    - numbers (int/float)
    - parentheses
    - unary +/-
    - +, -, *, /
    """

    expr = (expr or "").strip()
    if not expr:
        raise CalculatorError("Expression is required.")

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise CalculatorError("Invalid expression syntax.") from e

    node_count = 0

    def walk(node: ast.AST) -> float:
        nonlocal node_count
        node_count += 1
        if node_count > cfg.max_nodes:
            raise CalculatorError("Expression is too complex.")

        if isinstance(node, ast.Expression):
            return walk(node.body)

        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)

        # Python <3.8 compatibility (harmless in 3.13 but kept defensive)
        if hasattr(ast, "Num") and isinstance(node, ast.Num):  # type: ignore[attr-defined]
            return float(node.n)  # type: ignore[attr-defined]

        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = walk(node.operand)
            return v if isinstance(node.op, ast.UAdd) else -v

        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left = walk(node.left)
            right = walk(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            # Div
            if right == 0:
                raise CalculatorError("Division by zero.")
            return left / right

        raise CalculatorError("Only basic arithmetic is supported: + - * / and parentheses.")

    return walk(tree)


def calculator(args: JsonDict) -> JsonDict:
    """
    Tool function.
    Args: { "expression": "1 + 2 * (3 - 4.5)" }
    """

    expr = str(args.get("expression", "")).strip()
    try:
        value = _eval_expr(expr)
        # Return int-like values as int for nicer UX
        if value.is_integer():
            return {"ok": True, "expression": expr, "result": int(value)}
        return {"ok": True, "expression": expr, "result": value}
    except CalculatorError as e:
        return {"ok": False, "expression": expr, "error": str(e)}


def calculator_tool() -> Tool:
    return Tool(
        name="calculator",
        description="Evaluate a basic arithmetic expression (+ - * /, parentheses).",
        args_schema={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Arithmetic expression, e.g. '1 + 2 * (3 - 4)'.",
                }
            },
            "required": ["expression"],
        },
        fn=calculator,
    )

