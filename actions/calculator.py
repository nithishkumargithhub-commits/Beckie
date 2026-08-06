"""
Offline Calculator Action using safe AST expression evaluation.
Execution latency: ~20ms
"""

import ast
import operator
from logger import profile, get_logger

logger = get_logger("Jarvis.Actions.Calculator")

# Safe math operators mapping
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg
}

def safe_eval(node):
    if isinstance(node, ast.Num):
        return node.n
    elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    elif isinstance(node, ast.BinOp):
        left = safe_eval(node.left)
        right = safe_eval(node.right)
        return OPERATORS[type(node.op)](left, right)
    elif isinstance(node, ast.UnaryOp):
        operand = safe_eval(node.operand)
        return OPERATORS[type(node.op)](operand)
    else:
        raise ValueError("Unsupported mathematical operation")

@profile
def calculate_expression(expression: str) -> str:
    """Safely evaluates spoken arithmetic expressions."""
    try:
        clean_expr = expression.lower().replace("plus", "+").replace("minus", "-").replace("times", "*").replace("divided by", "/").replace("x", "*")
        clean_expr = "".join([c for c in clean_expr if c in "0123456789+-*/.() "])
        if not clean_expr.strip():
            return "Could not extract mathematical expression."
        
        parsed = ast.parse(clean_expr.strip(), mode='eval')
        result = safe_eval(parsed.body)
        return f"The answer is {result}."
    except Exception as e:
        logger.error(f"Error calculating expression '{expression}': {e}")
        return "Could not calculate the requested math problem."
