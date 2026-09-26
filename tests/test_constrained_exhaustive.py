"""Brute-force integer cross-validation of ratio-constrained balancing.

Every small signed conservation matrix is stacked with one or two approved
ratio rows (``q * c[a] - p * c[b] == 0``) and the constrained verdict is
compared against an *independent* integer-only oracle shared with
``test_exhaustive``:

* constrained ``nullity`` comes from exact integer determinants (Laplace
  expansion) of the stacked matrix — no fraction elimination shared with
  the code under test;
* a rank ``n - 1`` constrained null vector is built from signed
  (n-1)x(n-1) minors, directly giving the primitive integer vector;
* certified coefficients must satisfy every conservation row, every ratio
  row, be all-positive, and be primitive (overall gcd 1).

This guards against ratio constraints being solved by hand-picking free
variables: only a genuinely one-dimensional constrained null space may
produce a certificate.
"""

from __future__ import annotations

from itertools import permutations, product
from math import gcd

import pytest

from app.balancer import (
    BALANCED,
    NO_BALANCE,
    NO_POSITIVE_BALANCE,
    UNDERDETERMINED,
    Ratio,
    balance_constrained,
)
from test_exhaustive import (
    generate_matrices,
    integer_null_vector,
    matrix_rank,
    matrix_to_compounds,
)


def ratio_row(cols: int, a: int, b: int, p: int, q: int) -> list[int]:
    row = [0] * cols
    row[a] = q
    row[b] = -p
    return row


def ratio_sets(cols: int, count: int, coef_bound: int):
    """All ordered ratio lists of the given length over column pairs."""
    pairs = [(a, b) for a, b in permutations(range(cols), 2)]
    coefs = list(product(range(1, coef_bound + 1), repeat=2))
    singles = [(a, b, p, q) for (a, b) in pairs for (p, q) in coefs]
    if count == 1:
        return [[spec] for spec in singles]
    return [[first, second] for first in singles for second in singles]


def check_constrained(matrix, r_count, cols, specs, status_counts):
    compounds = matrix_to_compounds(matrix, r_count, cols)
    ratios = [
        Ratio(a=f"C{a}", b=f"C{b}", a_coefficient=p, b_coefficient=q)
        for a, b, p, q in specs
    ]
    result = balance_constrained(compounds, ratios)

    # Independent oracle: stacked integer matrix, rank via determinants.
    stacked = [list(row) for row in matrix] + [
        ratio_row(cols, a, b, p, q) for a, b, p, q in specs
    ]
    expected_nullity = cols - matrix_rank(stacked)

    assert result["nullity"] == expected_nullity
    status_counts[result["status"]] += 1

    # The ratio basis is echoed verbatim, whatever the verdict.
    assert result["ratios"] == [
        {"a": f"C{a}", "b": f"C{b}", "a_coefficient": p, "b_coefficient": q}
        for a, b, p, q in specs
    ]

    if expected_nullity == 0:
        assert result["status"] == NO_BALANCE
        return 0

    if expected_nullity >= 2:
        assert result["status"] == UNDERDETERMINED
        return 0

    oracle = integer_null_vector(stacked, cols)
    if any(v == 0 for v in oracle):
        assert result["status"] == NO_POSITIVE_BALANCE
        return 0
    if not (all(v > 0 for v in oracle) or all(v < 0 for v in oracle)):
        assert result["status"] == NO_POSITIVE_BALANCE
        return 0

    assert result["status"] == BALANCED
    overall = 0
    for v in oracle:
        overall = gcd(overall, abs(v))
    oriented = [abs(v) // overall for v in oracle]
    certified = [result["coefficients"][f"C{c}"] for c in range(cols)]
    assert certified == oriented

    # Certified vector is primitive, conserved, and ratio-exact.
    g = 0
    for v in certified:
        g = gcd(g, v)
    assert g == 1
    for row in stacked:
        assert sum(a * b for a, b in zip(row, certified)) == 0
    for a, b, p, q in specs:
        assert certified[a] * q == certified[b] * p
    # Signal for the caller: integerization actually reduced something.
    return 1 if overall > 1 else 0


@pytest.mark.parametrize("elements,cols,max_count", [(1, 3, 2), (2, 3, 2)])
def test_exhaustive_single_ratio(elements, cols, max_count):
    status_counts = {BALANCED: 0, NO_BALANCE: 0, UNDERDETERMINED: 0, NO_POSITIVE_BALANCE: 0}
    integerized = 0
    checked = 0
    for matrix, r_count in generate_matrices(elements, cols, max_count=max_count):
        for specs in ratio_sets(cols, count=1, coef_bound=2):
            integerized += check_constrained(matrix, r_count, cols, specs, status_counts)
            checked += 1

    assert checked == {1: 16, 2: 992}[elements] * 6 * 4
    # One ratio row on a 3-column system can never leave nullity >= 2:
    # rank(conservation) >= 1 and a two-nonzero ratio row is independent of
    # any single all-nonzero conservation row, so rank >= 2 always.
    assert status_counts[UNDERDETERMINED] == 0
    assert status_counts[BALANCED] > 0
    assert status_counts[NO_POSITIVE_BALANCE] > 0
    if elements == 1:
        # Two rows can never reach rank 3: contradiction is impossible.
        assert status_counts[NO_BALANCE] == 0
    else:
        # Rank-2 conservation + an independent ratio row -> nullity 0.
        assert status_counts[NO_BALANCE] > 0
    # Integerization with a non-trivial gcd was exercised.
    assert integerized > 0


def test_exhaustive_two_ratios_contradiction_and_uniqueness():
    status_counts = {BALANCED: 0, NO_BALANCE: 0, UNDERDETERMINED: 0, NO_POSITIVE_BALANCE: 0}
    checked = 0
    for matrix, r_count in generate_matrices(1, 3, max_count=2):
        for specs in ratio_sets(3, count=2, coef_bound=2):
            check_constrained(matrix, r_count, 3, specs, status_counts)
            checked += 1

    assert checked == 16 * 24 * 24
    # Two ratio rows on 3 columns: nullity 0 (contradictory) and nullity 1
    # (redundant pair) both occur; nullity can never stay >= 2.
    assert status_counts[NO_BALANCE] > 0
    assert status_counts[BALANCED] > 0
    assert status_counts[NO_POSITIVE_BALANCE] > 0
    assert status_counts[UNDERDETERMINED] == 0


def test_exhaustive_single_ratio_leaves_four_column_system_underdetermined():
    """One ratio on a rank-1, 4-column system: nullity drops 3 -> 2, never less."""
    checked = 0
    for matrix, r_count in generate_matrices(1, 4, max_count=2):
        for specs in ratio_sets(4, count=1, coef_bound=2):
            compounds = matrix_to_compounds(matrix, r_count, 4)
            ratios = [
                Ratio(a=f"C{a}", b=f"C{b}", a_coefficient=p, b_coefficient=q)
                for a, b, p, q in specs
            ]
            result = balance_constrained(compounds, ratios)
            stacked = [list(row) for row in matrix] + [
                ratio_row(4, a, b, p, q) for a, b, p, q in specs
            ]
            assert result["nullity"] == 4 - matrix_rank(stacked) == 2
            assert result["status"] == UNDERDETERMINED
            checked += 1
    assert checked == 48 * 12 * 4
