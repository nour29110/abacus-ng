"""
Pratt (precedence-climbing) parser for arithmetic expressions.

Grammar
-------
    expr   := term (('+' | '-') term)*
    term   := factor (('*' | '/') factor)*
    factor := power ('^' factor)?          # right-associative
    power  := ('-' power) | atom
    atom   := NUMBER | '(' expr ')'
"""
from __future__ import annotations

import re
from dataclasses import dataclass

INFIX_BP = {
    "+": (10, 11),
    "-": (10, 11),
    "*": (20, 21),
    "/": (20, 21),
    "^": (31, 30),  # right-associative: left_bp > right_bp
}
PREFIX_BP = 40  # unary minus binds tighter than any infix

@dataclass
class Token:
    kind: str
    value: float | None
    pos: int


class ParseError(ValueError):
    pass

_NUMBER_RE = re.compile(r"\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?")
_SINGLE_CHARS = {"+", "-", "*", "/", "^", "(", ")"}


def tokenize(src: str) -> list[Token]:
    """Tokenize *src* into a list of Tokens, ending with an EOF token."""
    tokens: list[Token] = []
    i = 0
    while i < len(src):
        ch = src[i]
        if ch.isspace():
            i += 1
            continue
        if ch in _SINGLE_CHARS:
            tokens.append(Token(kind=ch, value=None, pos=i))
            i += 1
            continue
        m = _NUMBER_RE.match(src, i)
        if m:
            tokens.append(Token(kind="NUMBER", value=float(m.group()), pos=i))
            i = m.end()
            continue
        raise ParseError(f"Unexpected character {ch!r} at position {i}")
    tokens.append(Token(kind="EOF", value=None, pos=len(src)))
    return tokens


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    def peek(self) -> Token:
        return self._tokens[self._pos]

    def eat(self, kind: str) -> Token:
        tok = self.peek()
        if tok.kind != kind:
            raise ParseError(
                f"Expected {kind!r} but got {tok.kind!r} at position {tok.pos}"
            )
        self._pos += 1
        return tok

    def parse(self) -> dict:
        node = self.expr(0)
        if self.peek().kind != "EOF":
            raise ParseError(f"Trailing input at {self.peek().pos}")
        return node

    def expr(self, min_bp: int) -> dict:
        tok = self.peek()
        # prefix / atom
        if tok.kind == "NUMBER":
            self._pos += 1
            left = {"type": "num", "value": tok.value}
        elif tok.kind == "(":
            self._pos += 1
            left = self.expr(0)
            if self.peek().kind != ")":
                raise ParseError("Missing closing paren")
            self._pos += 1
        elif tok.kind == "-":
            self._pos += 1
            right = self.expr(PREFIX_BP)
            left = {"type": "neg", "child": right}
        else:
            raise ParseError(f"Unexpected {tok.kind!r} at {tok.pos}")
        # infix loop
        while True:
            op = self.peek()
            if op.kind not in INFIX_BP:
                break
            l_bp, r_bp = INFIX_BP[op.kind]
            if l_bp < min_bp:
                break
            self._pos += 1
            right = self.expr(r_bp)
            left = {"type": "op", "op": op.kind, "left": left, "right": right}
        return left


def parse(src: str) -> dict:
    """Convenience: tokenize *src* and parse it in one call."""
    return Parser(tokenize(src)).parse()
