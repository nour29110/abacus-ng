"""
FastAPI entry point for abacus-ng.

Security approach (mirrors lessons from the webhook code review):
- Strict input validation via Pydantic (max_length caps request size).
- No eval / no exec — expression evaluation uses a hand-rolled parser
  (see parser.py) and an explicit AST walker (see evaluator.py).
- Explicit error handling: ParseError and EvalError map to 400 responses
  rather than leaking generic 500s.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from parser import parse, ParseError
from evaluator import evaluate, EvalError

MAX_EXPR_LEN = 256

app = FastAPI(title="abacus-ng", version="1.0.0")

# Allow all origins — acceptable for local dev only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class CalcRequest(BaseModel):
    expression: str = Field(..., min_length=1, max_length=MAX_EXPR_LEN)


class CalcResponse(BaseModel):
    result: float
    ast: dict
    expression: str


@app.post("/api/calc", response_model=CalcResponse)
def calc(req: CalcRequest):
    try:
        ast = parse(req.expression)
    except ParseError as e:
        raise HTTPException(400, f"parse error: {e}")
    try:
        result = evaluate(ast)
    except EvalError as e:
        raise HTTPException(400, f"eval error: {e}")
    return CalcResponse(result=result, ast=ast, expression=req.expression)


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
