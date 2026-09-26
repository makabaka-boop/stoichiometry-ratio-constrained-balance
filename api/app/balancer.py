"""Exact rational balancing core.

The conservation matrix has one row per element and one column per
compound. Reactant stoichiometric counts are positive and product counts
are negative, so a coefficient vector ``c`` is balanced exactly when
``M @ c == 0``. All arithmetic is done with :class:`fractions.Fraction`
so that near-zero pivot values produced by floating point elimination can
never be mistaken for real constraints.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import gcd
from typing import Iterable

REACTANT = "REACTANT"
PRODUCT = "PRODUCT"

BALANCED = "BALANCED"
NO_BALANCE = "NO_BALANCE"
UNDERDETERMINED = "UNDERDETERMINED"
NO_POSITIVE_BALANCE = "NO_POSITIVE_BALANCE"


@dataclass(frozen=True)
class Compound:
    id: str
    side: str
    composition: dict[str, int]


def _lcm(a: int, b: int) -> int:
    return a // gcd(a, b) * b


def ordered_elements(compounds: Iterable[Compound]) -> list[str]:
    """Element symbols in first-appearance order across the compound list."""
    seen: dict[str, None] = {}
    for compound in compounds:
        for symbol in compound.composition:
            seen.setdefault(symbol, None)
    return list(seen)


def build_matrix(
    compounds: list[Compound], elements: list[str]
) -> list[list[Fraction]]:
    sign = {REACTANT: 1, PRODUCT: -1}
    matrix: list[list[Fraction]] = []
    for symbol in elements:
        row: list[Fraction] = []
        for compound in compounds:
            count = compound.composition.get(symbol, 0)
            row.append(Fraction(sign[compound.side] * count))
        matrix.append(row)
    return matrix


def null_space(matrix: list[list[Fraction]], cols: int) -> list[list[Fraction]]:
    """Return a basis of the right null space via exact RREF elimination."""
    work = [row[:] for row in matrix]
    rows = len(work)
    pivot_cols: list[int] = []
    pivot_row = 0
    for col in range(cols):
        pivot = next(
            (r for r in range(pivot_row, rows) if work[r][col] != 0), None
        )
        if pivot is None:
            continue
        work[pivot_row], work[pivot] = work[pivot], work[pivot_row]
        pivot_value = work[pivot_row][col]
        work[pivot_row] = [v / pivot_value for v in work[pivot_row]]
        for r in range(rows):
            if r != pivot_row and work[r][col] != 0:
                factor = work[r][col]
                work[r] = [
                    value - factor * pivot_entry
                    for value, pivot_entry in zip(work[r], work[pivot_row])
                ]
        pivot_cols.append(col)
        pivot_row += 1

    free_cols = [c for c in range(cols) if c not in set(pivot_cols)]
    basis: list[list[Fraction]] = []
    for free in free_cols:
        vector = [Fraction(0)] * cols
        vector[free] = Fraction(1)
        for row_index, pivot_col in enumerate(pivot_cols):
            vector[pivot_col] = -work[row_index][free]
        basis.append(vector)
    return basis


def _to_primitive_ints(vector: list[Fraction]) -> list[int]:
    denominator_lcm = 1
    for value in vector:
        denominator_lcm = _lcm(denominator_lcm, value.denominator)
    integers = [int(value * denominator_lcm) for value in vector]
    overall_gcd = 0
    for value in integers:
        overall_gcd = gcd(overall_gcd, abs(value))
    if overall_gcd > 1:
        integers = [value // overall_gcd for value in integers]
    return integers


def _element_totals(
    compounds: list[Compound],
    elements: list[str],
    coefficients: dict[str, int],
) -> list[dict[str, object]]:
    totals: list[dict[str, object]] = []
    for symbol in elements:
        reactant_total = 0
        product_total = 0
        for compound in compounds:
            amount = coefficients.get(compound.id, 0) * compound.composition.get(
                symbol, 0
            )
            if compound.side == REACTANT:
                reactant_total += amount
            else:
                product_total += amount
        totals.append(
            {
                "element": symbol,
                "reactant": reactant_total,
                "product": product_total,
                "balanced": reactant_total == product_total,
            }
        )
    return totals


def _format_equation(
    compounds: list[Compound], coefficients: dict[str, int]
) -> str:
    def terms(side: str) -> str:
        parts = []
        for compound in compounds:
            if compound.side != side:
                continue
            coefficient = coefficients[compound.id]
            parts.append(
                compound.id if coefficient == 1 else f"{coefficient} {compound.id}"
            )
        return " + ".join(parts)

    return f"{terms(REACTANT)} -> {terms(PRODUCT)}"


def balance(compounds: list[Compound]) -> dict[str, object]:
    """Balance one validated compound set and return the full verdict payload."""
    elements = ordered_elements(compounds)
    matrix = build_matrix(compounds, elements)
    basis = null_space(matrix, len(compounds))
    nullity = len(basis)

    result: dict[str, object] = {
        "status": None,
        "nullity": nullity,
        "elements": elements,
        "compound_ids": [compound.id for compound in compounds],
    }

    if nullity == 0:
        result["status"] = NO_BALANCE
        result["reason"] = "Null space is empty: conservation constraints are inconsistent."
        return result

    if nullity > 1:
        result["status"] = UNDERDETERMINED
        result["reason"] = (
            f"Null space has dimension {nullity}: multiple stoichiometric "
            "families exist, so no unique recipe can be certified."
        )
        return result

    vector = basis[0]
    if any(value == 0 for value in vector):
        result["status"] = NO_POSITIVE_BALANCE
        result["reason"] = "The unique null vector assigns a zero coefficient to at least one compound."
        return result

    if all(value > 0 for value in vector):
        oriented = vector
    elif all(value < 0 for value in vector):
        oriented = [-value for value in vector]
    else:
        result["status"] = NO_POSITIVE_BALANCE
        result["reason"] = "The unique null vector mixes positive and negative entries."
        return result

    integers = _to_primitive_ints(oriented)
    coefficients = {
        compound.id: value for compound, value in zip(compounds, integers)
    }
    result["status"] = BALANCED
    result["coefficients"] = coefficients
    result["element_totals"] = _element_totals(compounds, elements, coefficients)
    result["equation"] = _format_equation(compounds, coefficients)
    return result


def review(
    compounds: list[Compound], coefficients: dict[str, int]
) -> dict[str, object]:
    """Independently re-check a human-entered coefficient assignment."""
    elements = ordered_elements(compounds)
    compound_ids = [compound.id for compound in compounds]
    missing_ids = [cid for cid in compound_ids if cid not in coefficients]
    unknown_ids = [cid for cid in coefficients if cid not in set(compound_ids)]

    element_totals = _element_totals(compounds, elements, coefficients)
    unbalanced = [row["element"] for row in element_totals if not row["balanced"]]

    entered = [coefficients.get(cid, 0) for cid in compound_ids]
    non_positive = [
        cid for cid, value in zip(compound_ids, entered) if value <= 0
    ]

    positive_values = [value for value in entered if value > 0]
    overall_gcd = 0
    for value in positive_values:
        overall_gcd = gcd(overall_gcd, abs(value))
    is_primitive = bool(positive_values) and overall_gcd == 1 and not non_positive

    reasons: list[str] = []
    if missing_ids:
        reasons.append("MISSING_COEFFICIENTS")
    if unknown_ids:
        reasons.append("UNKNOWN_COEFFICIENT_IDS")
    if non_positive:
        reasons.append("NON_POSITIVE_COEFFICIENT")
    if unbalanced:
        reasons.append("NOT_CONSERVED")
    if positive_values and overall_gcd > 1 and not non_positive:
        reasons.append("NOT_PRIMITIVE")

    return {
        "valid": not reasons,
        "reasons": reasons,
        "gcd": overall_gcd if positive_values else None,
        "primitive": is_primitive,
        "missing_ids": missing_ids,
        "unknown_ids": unknown_ids,
        "non_positive_ids": non_positive,
        "unbalanced_elements": unbalanced,
        "elements": element_totals,
    }
