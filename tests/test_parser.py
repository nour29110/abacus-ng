import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from parser import parse, ParseError
from evaluator import evaluate, EvalError


def calc(s):
    return evaluate(parse(s))


def test_basic():
    assert calc("1 + 2") == 3
    assert calc("2 * 3 + 4") == 10
    assert calc("2 + 3 * 4") == 14


def test_precedence_and_parens():
    assert calc("(2 + 3) * 4") == 20
    assert calc("2 ^ 3 ^ 2") == 512
    assert calc("(2 ^ 3) ^ 2") == 64


def test_unary():
    assert calc("-5 + 3") == -2
    assert calc("-(2 + 3)") == -5
    assert calc("- -5") == 5


def test_division_by_zero():
    with pytest.raises(EvalError):
        calc("1/0")


def test_huge_exponent_blocked():
    with pytest.raises(EvalError):
        calc("10 ^ 10000")


def test_garbage_rejected():
    for expr in ["", "1 +", "((1)", "1 2", "1 + + 2", "abc", "1..2"]:
        with pytest.raises((ParseError, EvalError)):
            calc(expr)


def test_scientific_notation():
    assert calc("1e3") == 1000
    assert calc("1.5e2") == 150
    assert calc("2e-1 * 10") == 2
