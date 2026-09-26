"""Structural + semantic request validation.

Structural problems (unknown fields, wrong types, bad ``side`` literal,
wrong compound count) come from Pydantic and are translated into the
same issue shape as semantic problems (duplicate IDs, illegal element
symbols, empty compositions, ...). A batch is rejected wholesale as soon
as any issue exists; partial results are never computed.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from .balancer import Compound
from .elements import ELEMENT_SYMBOLS
from .schemas import BalanceRequest, CompoundIn, ReviewRequest

MAX_COMPOUNDS = 12
MIN_COMPOUNDS = 2
MAX_ELEMENTS = 20
MAX_ID_LENGTH = 64


def _issue(
    code: str,
    message: str,
    *,
    loc: str | None = None,
    compound_id: str | None = None,
    element: str | None = None,
    value: Any = None,
) -> dict[str, Any]:
    issue: dict[str, Any] = {"code": code, "message": message}
    if loc is not None:
        issue["loc"] = loc
    if compound_id is not None:
        issue["compound_id"] = compound_id
    if element is not None:
        issue["element"] = element
    if value is not None:
        issue["value"] = value
    return issue


def _translate_pydantic(exc: ValidationError) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error["loc"]) or "."
        error_type = error["type"]
        if error_type == "extra_forbidden":
            extra_name = error.get("ctx", {}).get("extra")
            issues.append(
                _issue(
                    "UNKNOWN_FIELD",
                    f"Unknown field {extra_name!r}." if extra_name else "Unknown field.",
                    loc=loc,
                    value=extra_name,
                )
            )
        elif error_type == "missing":
            issues.append(
                _issue("MISSING_FIELD", "Required field is missing.", loc=loc)
            )
        elif error_type == "literal_error":
            issues.append(
                _issue(
                    "INVALID_SIDE",
                    "side must be REACTANT or PRODUCT.",
                    loc=loc,
                    value=error.get("input"),
                )
            )
        elif error_type in ("too_short", "too_long"):
            issues.append(
                _issue(
                    "INVALID_COMPOUND_COUNT",
                    f"compounds must contain between {MIN_COMPOUNDS} and "
                    f"{MAX_COMPOUNDS} unique entries.",
                    loc=loc,
                    value=error.get("input") if not isinstance(error.get("input"), list)
                    else len(error["input"]),
                )
            )
        elif error_type in ("int_type", "int_parsing", "int_from_float"):
            issues.append(
                _issue("INVALID_INTEGER", "Value must be an integer.", loc=loc)
            )
        elif error_type == "string_type":
            issues.append(
                _issue("INVALID_ID", "id must be an ASCII string.", loc=loc)
            )
        else:
            issues.append(
                _issue(
                    "REQUEST_MALFORMED",
                    f"{error_type}: {error.get('msg', 'malformed request')}",
                    loc=loc,
                )
            )
    return issues


def _semantic_compound_issues(raw: CompoundIn, index: int) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    loc = f"compounds[{index}]"
    compound_id = raw.id

    if compound_id == "":
        issues.append(
            _issue("EMPTY_ID", "Compound id must be a non-empty ASCII string.", loc=loc)
        )
    elif not compound_id.isascii():
        issues.append(
            _issue(
                "NON_ASCII_ID",
                "Compound id must contain ASCII characters only.",
                loc=f"{loc}.id",
                compound_id=compound_id,
            )
        )
    elif len(compound_id) > MAX_ID_LENGTH:
        issues.append(
            _issue(
                "ID_TOO_LONG",
                f"Compound id must be at most {MAX_ID_LENGTH} characters.",
                loc=f"{loc}.id",
                compound_id=compound_id,
            )
        )

    if not raw.composition:
        issues.append(
            _issue(
                "EMPTY_COMPOSITION",
                "Composition must list at least one element.",
                loc=f"{loc}.composition",
                compound_id=compound_id or None,
            )
        )

    for symbol, count in raw.composition.items():
        if count <= 0:
            issues.append(
                _issue(
                    "NON_POSITIVE_COUNT",
                    "Element counts must be positive integers.",
                    loc=f"{loc}.composition.{symbol}",
                    compound_id=compound_id or None,
                    element=symbol,
                    value=count,
                )
            )

        if symbol not in ELEMENT_SYMBOLS:
            issues.append(
                _issue(
                    "INVALID_ELEMENT",
                    f"'{symbol}' is not a recognized element symbol.",
                    loc=f"{loc}.composition.{symbol}",
                    compound_id=compound_id or None,
                    element=symbol,
                )
            )
    return issues


def parse_compounds(payload: Any) -> tuple[list[Compound] | None, list[dict[str, Any]]]:
    try:
        request = BalanceRequest.model_validate(payload)
    except ValidationError as exc:
        return None, _translate_pydantic(exc)

    issues: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    element_symbols: set[str] = set()

    for index, raw in enumerate(request.compounds):
        if raw.id and raw.id in seen_ids:
            issues.append(
                _issue(
                    "DUPLICATE_ID",
                    f"Duplicate compound id '{raw.id}': IDs must be unique.",
                    loc=f"compounds[{index}].id",
                    compound_id=raw.id,
                )
            )
        if raw.id:
            seen_ids.add(raw.id)
        issues.extend(_semantic_compound_issues(raw, index))
        element_symbols.update(raw.composition.keys())

    if element_symbols and len(element_symbols) > MAX_ELEMENTS:
        issues.append(
            _issue(
                "TOO_MANY_ELEMENTS",
                f"There are {len(element_symbols)} distinct elements; the limit is {MAX_ELEMENTS}.",
                value=len(element_symbols),
            )
        )

    if issues:
        return None, issues

    compounds = [
        Compound(
            id=raw.id,
            side=raw.side,
            composition={symbol: int(count) for symbol, count in raw.composition.items()},
        )
        for raw in request.compounds
    ]
    return compounds, []


def parse_review_payload(
    payload: Any,
) -> tuple[tuple[list[Compound], dict[str, int]] | None, list[dict[str, Any]]]:
    try:
        request = ReviewRequest.model_validate(payload)
    except ValidationError as exc:
        return None, _translate_pydantic(exc)

    compounds, issues = parse_compounds(
        {"compounds": [raw.model_dump() for raw in request.compounds]}
    )
    if issues:
        return None, issues

    coefficients = {
        cid: int(value) for cid, value in request.coefficients.items()
    }
    return (compounds, coefficients), []
