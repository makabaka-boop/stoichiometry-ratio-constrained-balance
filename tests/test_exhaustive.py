"""Brute-force integer cross-validation of the rational balancer.

For every small signed conservation matrix (reactant columns carry
positive composition entries, product columns negative entries) the
balancer's verdict is compared against an *independent* integer-only
oracle:

* ``nullity`` is derived from exact integer determinants (Laplace
  expansion, no fraction elimination shared with the code under test);
* a rank ``n - 1`` null vector is built from signed (n-1)x(n-1)
  minors, which directly produces the primitive integer vector;
* positive solutions are cross-checked by exhaustive enumeration of
  bounded primitive vectors.

This specifically guards against floating-point elimination treating an
approximate zero as a constraint, and against free variables being
hand-picked so that a multi-dimensional system masquerades as unique.
"""

from __future__ import annotations

from fractions import Fraction
from itertools import combinations, product

import pytest

from app.balancer import (
    BALANCED,
    NO_BALANCE,
    NO_POSITIVE_BALANCE,
    UNDERDETERMINED,
    Compound,
    balance,
)


def det(matrix: tuple[tuple[int, ...], ...]) -> int:
    n = len(matrix)
    if n == 1:
        return matrix[0][0]
    total = 0
    for col in range(n):
        minor = tuple(
            tuple(matrix[r][c] for c in range(n) if c != col)
            for r in range(1, n)
        )
        sign = 1 if col % 2 == 0 else -1
        total += sign * matrix[0][col] * det(minor)
    return total


def matrix_rank(matrix: list[list[int]]) -> int:
    rows = len(matrix)
    cols = len(matrix[0])
    for size in range(min(rows, cols), 0, -1):
        for row_set in combinations(range(rows), size):
            for col_set in combinations(range(cols), size):
                sub = tuple(
                    tuple(matrix[r][c] for c in col_set) for r in row_set
                )
                if det(sub) != 0:
                    return size
    return 0


def integer_null_vector(matrix: list[list[int]], cols: int) -> list[int]:
    """Primitive-proportional integer null vector when rank == cols - 1.

    Fix one set of ``cols - 1`` rows of full row rank and take the signed
    maximal minors (delete each column in turn from that fixed submatrix).
    Cofactor expansion guarantees the result is orthogonal to the chosen
    rows; since the full matrix has rank ``cols - 1`` all other rows lie
    in their span, so it is a null vector of the complete matrix.
    """
    chosen_rows = None
    for row_set in combinations(range(len(matrix)), cols - 1):
        for col_set in combinations(range(cols), cols - 1):
            square = tuple(
                tuple(matrix[r][c] for c in col_set) for r in row_set
            )
            if det(square) != 0:
                chosen_rows = row_set
                break
        if chosen_rows is not None:
            break
    assert chosen_rows is not None, "rank n-1 must leave a non-singular row set"

    vector = []
    for removed in range(cols):
        kept = [c for c in range(cols) if c != removed]
        square = tuple(
            tuple(matrix[r][c] for c in kept) for r in chosen_rows
        )
        sign = 1 if removed % 2 == 0 else -1
        vector.append(sign * det(square))
    return vector


def primitive_positive_solutions(
    matrix: list[list[int]], bound: int
) -> list[tuple[int, ...]]:
    cols = len(matrix[0])
    solutions = []
    for candidate in product(range(1, bound + 1), repeat=cols):
        for row in matrix:
            if sum(entry * coefficient for entry, coefficient in zip(row, candidate)) != 0:
                break
        else:
            from math import gcd

            overall = 0
            for value in candidate:
                overall = gcd(overall, value)
            if overall == 1:
                solutions.append(candidate)
    return solutions


def generate_matrices(elements: int, cols: int, max_count: int):
    """All distinct signed composition matrices with the given dimensions.

    Each cell takes 0..max_count; reactant columns are positive, product
    columns negative. Columns that are entirely zero (empty compositions,
    rejected by the API) are skipped, while all-zero rows are merely
    de-duplicated so one matrix shape is never yielded twice.
    """
    seen: set[tuple[tuple[int, ...], ...]] = set()
    for r_count in range(1, cols):
        signs = [1] * r_count + [-1] * (cols - r_count)
        cell_values = range(0, max_count + 1)
        for composition in product(cell_values, repeat=elements * cols):
            matrix = [
                [
                    composition[e * cols + c] * signs[c]
                    for c in range(cols)
                ]
                for e in range(elements)
            ]
            if any(all(matrix[e][c] == 0 for e in range(elements)) for c in range(cols)):
                continue
            trimmed = []
            for row in matrix:
                if all(v == 0 for v in row):
                    continue
                key = tuple(row)
                if key not in {tuple(existing) for existing in trimmed}:
                    trimmed.append(row)
            key = tuple(tuple(row) for row in trimmed)
            if key in seen:
                continue
            seen.add(key)
            yield trimmed, r_count


def matrix_to_compounds(matrix, r_count, cols):
    compounds = []
    for c in range(cols):
        side = "REACTANT" if c < r_count else "PRODUCT"
        composition = {
            f"E{e}": matrix[e][c] * (1 if c < r_count else -1)
            for e in range(len(matrix))
            if matrix[e][c] != 0
        }
        compounds.append(Compound(id=f"C{c}", side=side, composition=composition))
    return compounds


@pytest.mark.parametrize(
    "elements,cols,max_count",
    [(1, 2, 3), (1, 3, 2), (2, 2, 3), (2, 3, 2), (3, 3, 2)],
)
def test_exhaustive_small_matrices(elements, cols, max_count):
    checked = 0
    status_counts = {BALANCED: 0, NO_BALANCE: 0, UNDERDETERMINED: 0, NO_POSITIVE_BALANCE: 0}
    for matrix, r_count in generate_matrices(elements, cols, max_count=max_count):
        compounds = matrix_to_compounds(matrix, r_count, cols)
        result = balance(compounds)
        rank = matrix_rank(matrix)
        expected_nullity = cols - rank

        assert result["nullity"] == expected_nullity
        status_counts[result["status"]] += 1

        if expected_nullity == 0:
            assert result["status"] == NO_BALANCE

        elif expected_nullity >= 2:
            assert result["status"] == UNDERDETERMINED
            # Independent check: the basis returned by Fraction RREF must
            # actually span an expected_nullity-dimensional space.
            from app.balancer import build_matrix, null_space, ordered_elements

            symbols = ordered_elements(compounds)
            rational = build_matrix(compounds, symbols)
            basis = null_space(rational, cols)
            assert len(basis) == expected_nullity

        else:  # nullity == 1
            oracle = integer_null_vector(matrix, cols)
            if any(v == 0 for v in oracle):
                assert result["status"] == NO_POSITIVE_BALANCE
            else:
                same_sign = all(v > 0 for v in oracle) or all(v < 0 for v in oracle)
                if not same_sign:
                    assert result["status"] == NO_POSITIVE_BALANCE
                else:
                    assert result["status"] == BALANCED
                    from math import gcd

                    overall = 0
                    for v in oracle:
                        overall = gcd(overall, abs(v))
                    oriented = [abs(v) // overall for v in oracle]
                    certified = [result["coefficients"][f"C{c}"] for c in range(cols)]
                    assert certified == oriented
                    # Returned coefficients must be primitive by construction.
                    g = 0
                    for v in certified:
                        g = gcd(g, v)
                    assert g == 1
                    # And the certified primitive vector multiplies in exactly.
                    for row in matrix:
                        assert sum(a * b for a, b in zip(row, certified)) == 0
                    # It must be the unique bounded primitive positive solution.
                    solutions = primitive_positive_solutions(matrix, max(certified))
                    assert tuple(certified) in solutions
                    assert solutions.count(tuple(certified)) == 1
        checked += 1

    # Enumeration actually exercised the space, and each possible verdict
    # class appeared at least once for these dimensions.
    assert checked == {
        (1, 2, 3): 9, (1, 3, 2): 16, (2, 2, 3): 207,
        (2, 3, 2): 992, (3, 3, 2): 30176,
    }[(elements, cols, max_count)]
    # A single element row can only yield BALANCED (2 columns: one scalar
    # equation with 2 unknowns) or UNDERDETERMINED (>=3 columns); rank can
    # never reach column count, and non-zero columns rule out zero null
    # vectors. Those two boundary cases assert exactly that.
    if elements == 1 and cols == 2:
        assert status_counts == {
            BALANCED: 9, NO_BALANCE: 0, UNDERDETERMINED: 0, NO_POSITIVE_BALANCE: 0
        }
    elif elements == 1 and cols == 3:
        assert status_counts == {
            BALANCED: 0, NO_BALANCE: 0, UNDERDETERMINED: 16, NO_POSITIVE_BALANCE: 0
        }
    elif cols == 2:
        # Signed two-column null vectors are always strictly positive:
        # no zero components and no mixed signs are reachable.
        assert status_counts[BALANCED] > 0
        assert status_counts[NO_BALANCE] > 0
        assert status_counts[UNDERDETERMINED] == 0
        assert status_counts[NO_POSITIVE_BALANCE] == 0
    else:
        assert status_counts[BALANCED] > 0
        assert status_counts[UNDERDETERMINED] > 0
        assert status_counts[NO_POSITIVE_BALANCE] > 0
        # Nullity zero needs at least as many element rows as columns.
        if elements >= cols:
            assert status_counts[NO_BALANCE] > 0


def test_exhaustive_2x4_underdetermined_space():
    """3-element, 4-column matrices focus specifically on nullity >= 2 cases."""
    seen_underdetermined = 0
    for matrix, r_count in generate_matrices(2, 4, max_count=1):
        compounds = matrix_to_compounds(matrix, r_count, 4)
        result = balance(compounds)
        rank = matrix_rank(matrix)
        expected_nullity = 4 - rank
        assert result["nullity"] == expected_nullity
        if expected_nullity >= 2:
            seen_underdetermined += 1
            assert result["status"] == UNDERDETERMINED
    assert seen_underdetermined > 0
