# The Honest Calculator 📏

A calculator web app that refuses to use `eval`. Every expression is tokenized and parsed by a hand-written Pratt parser, walked by a tiny tree-walking evaluator, and rendered live as an AST in the browser. It's probably overkill for `2 + 2`, but that's sort of the point.

> I built this as part of an engineering take-home. The take-home included a code review of a webhook with a SQL injection and a timing attack. I figured the deeper lesson was *don't take shortcuts with untrusted input* — so my calculator has no `eval`, no mathjs, no expression library. Just a parser I wrote myself. See [REVIEW.md](REVIEW.md).

## Why it's interesting

- **No `eval`, no expression libs.** ~150 lines of hand-written parser + evaluator.
- **Shows its work.** The frontend renders the AST as an SVG tree that updates as you type.
- **Safe by construction.** Input size capped, exponents bounded (no `10**10**10` DoS), division by zero caught, tokenizer rejects anything outside the grammar.
- **Zero frontend dependencies.** No React, no bundler. Vanilla JS, one HTML file, one CSS file.
- **Tested.** pytest suite covers precedence, associativity, unary minus, and adversarial inputs.

## Run it

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
# open http://localhost:8080
```

## Structure

```
backend/    FastAPI + Pratt parser + evaluator
frontend/   vanilla JS, SVG tree renderer
tests/      pytest
REVIEW.md   code review of the take-home webhook PR
PROMPTS.md  AI prompts I used and what worked
```

## Grammar

```
expr    := term   (('+' | '-') term)*
term    := factor (('*' | '/') factor)*
factor  := power  ('^' factor)?          # right-associative
power   := ('-' power) | atom
atom    := NUMBER | '(' expr ')'
```

## If I had more time

- Variables and `let` bindings (one more token type + a scope dict).
- Function calls (`sin`, `cos`, `sqrt`) via a whitelist — still no `eval`.
- Rational arithmetic with Python's `fractions` so `1/3 * 3 == 1` exactly.
- A "step-through" mode that animates the evaluator walking the tree.
