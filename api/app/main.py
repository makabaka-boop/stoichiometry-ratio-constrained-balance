"""FastAPI entrypoint for the stoichiometric balancing workbench."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .balancer import balance, balance_constrained, review, review_constrained
from .validation import (
    parse_compounds,
    parse_constrained_balance_payload,
    parse_constrained_review_payload,
    parse_review_payload,
)

app = FastAPI(
    title="Stoichiometric Balancing Workbench",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/balance")
async def post_balance(request: Request) -> JSONResponse:
    payload = await _json_body(request)
    if not isinstance(payload, dict):
        return _validation_error([
            {"code": "REQUEST_MALFORMED", "message": "Request body must be a JSON object."}
        ])
    compounds, issues = parse_compounds(payload)
    if issues:
        return _validation_error(issues)
    assert compounds is not None
    return JSONResponse(balance(compounds))


@app.post("/api/review")
async def post_review(request: Request) -> JSONResponse:
    payload = await _json_body(request)
    if not isinstance(payload, dict):
        return _validation_error([
            {"code": "REQUEST_MALFORMED", "message": "Request body must be a JSON object."}
        ])
    parsed, issues = parse_review_payload(payload)
    if issues:
        return _validation_error(issues)
    assert parsed is not None
    compounds, coefficients = parsed
    return JSONResponse(review(compounds, coefficients))


@app.post("/api/balance/constrained")
async def post_balance_constrained(request: Request) -> JSONResponse:
    payload = await _json_body(request)
    if not isinstance(payload, dict):
        return _validation_error([
            {"code": "REQUEST_MALFORMED", "message": "Request body must be a JSON object."}
        ])
    parsed, issues = parse_constrained_balance_payload(payload)
    if issues:
        return _validation_error(issues)
    assert parsed is not None
    compounds, ratios = parsed
    return JSONResponse(balance_constrained(compounds, ratios))


@app.post("/api/review/constrained")
async def post_review_constrained(request: Request) -> JSONResponse:
    payload = await _json_body(request)
    if not isinstance(payload, dict):
        return _validation_error([
            {"code": "REQUEST_MALFORMED", "message": "Request body must be a JSON object."}
        ])
    parsed, issues = parse_constrained_review_payload(payload)
    if issues:
        return _validation_error(issues)
    assert parsed is not None
    compounds, coefficients, ratios = parsed
    return JSONResponse(review_constrained(compounds, coefficients, ratios))


async def _json_body(request: Request) -> Any:
    try:
        return await request.json()
    except Exception:
        return None


def _validation_error(issues: list[dict[str, Any]]) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": "VALIDATION_FAILED", "issues": issues},
    )
