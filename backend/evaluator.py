"AST walker. Intentionally no eval, no exec, no dynamic dispatch."

import math


class EvalError(ValueError):
    pass


def evaluate(node: dict) -> float:
    t = node.get("type")

    if t == "num":
        v = node["value"]
        if not math.isfinite(v):
            raise EvalError("number out of range")
        return v

    if t == "neg":
        return -evaluate(node["child"])

    if t == "op":
        a = evaluate(node["left"])
        b = evaluate(node["right"])
        op = node["op"]
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if b == 0:
                raise EvalError("division by zero")
            return a / b
        if op == "^":
            if abs(b) > 1000 or abs(a) > 1e100:
                raise EvalError("exponent too large")
            return a ** b

    raise EvalError(f"bad node: {node.get('type')}")
