"""Known-equation unit tests for the exact rational balancer."""

from fractions import Fraction

from app.balancer import (
    BALANCED,
    NO_BALANCE,
    NO_POSITIVE_BALANCE,
    UNDERDETERMINED,
    Compound,
    balance,
    build_matrix,
    null_space,
    ordered_elements,
    review,
)


def C(cid, side, comp):
    return Compound(id=cid, side=side, composition=comp)


def test_water_electrolysis():
    result = balance([
        C("H2", "REACTANT", {"H": 2}),
        C("O2", "REACTANT", {"O": 2}),
        C("H2O", "PRODUCT", {"H": 2, "O": 1}),
    ])
    assert result["status"] == BALANCED
    assert result["coefficients"] == {"H2": 2, "O2": 1, "H2O": 2}
    assert result["equation"] == "2 H2 + O2 -> 2 H2O"
    totals = {row["element"]: row for row in result["element_totals"]}
    assert totals["H"] == {"element": "H", "reactant": 4, "product": 4, "balanced": True}
    assert totals["O"] == {"element": "O", "reactant": 2, "product": 2, "balanced": True}


def test_propane_combustion():
    result = balance([
        C("C3H8", "REACTANT", {"C": 3, "H": 8}),
        C("O2", "REACTANT", {"O": 2}),
        C("CO2", "PRODUCT", {"C": 1, "O": 2}),
        C("H2O", "PRODUCT", {"H": 2, "O": 1}),
    ])
    assert result["status"] == BALANCED
    assert result["coefficients"] == {"C3H8": 1, "O2": 5, "CO2": 3, "H2O": 4}


def test_kmno4_hcl():
    result = balance([
        C("KMnO4", "REACTANT", {"K": 1, "Mn": 1, "O": 4}),
        C("HCl", "REACTANT", {"H": 1, "Cl": 1}),
        C("KCl", "PRODUCT", {"K": 1, "Cl": 1}),
        C("MnCl2", "PRODUCT", {"Mn": 1, "Cl": 2}),
        C("H2O", "PRODUCT", {"H": 2, "O": 1}),
        C("Cl2", "PRODUCT", {"Cl": 2}),
    ])
    assert result["status"] == BALANCED
    assert result["coefficients"] == {
        "KMnO4": 2, "HCl": 16, "KCl": 2, "MnCl2": 2, "H2O": 8, "Cl2": 5
    }


def test_ammonia_oxidation_no_side():
    """Famous underdetermined in chemistry teaching: 4/4/2/6 etc. is unique here."""
    result = balance([
        C("NH3", "REACTANT", {"N": 1, "H": 3}),
        C("O2", "REACTANT", {"O": 2}),
        C("NO", "PRODUCT", {"N": 1, "O": 1}),
        C("H2O", "PRODUCT", {"H": 2, "O": 1}),
    ])
    assert result["status"] == BALANCED
    assert result["coefficients"] == {"NH3": 4, "O2": 5, "NO": 4, "H2O": 6}


def test_no_balance_disjoint_elements():
    result = balance([
        C("A", "REACTANT", {"H": 1}),
        C("B", "PRODUCT", {"O": 1}),
    ])
    assert result["status"] == NO_BALANCE
    assert result["nullity"] == 0


def test_underdetermined_three_columns_one_constraint():
    # A -> B + C where every compound carries one H: nullity 2.
    result = balance([
        C("A", "REACTANT", {"H": 1}),
        C("B", "PRODUCT", {"H": 1}),
        C("C", "PRODUCT", {"H": 1}),
    ])
    assert result["status"] == UNDERDETERMINED
    assert result["nullity"] == 2


def test_zero_component_unique_vector():
    # H: [1, 0, -1] and O: [0, 1, 0] -> unique vector (1, 0, 1), B unused.
    result = balance([
        C("A", "REACTANT", {"H": 1}),
        C("B", "REACTANT", {"O": 1}),
        C("C", "PRODUCT", {"H": 1}),
    ])
    assert result["status"] == NO_POSITIVE_BALANCE
    assert result["nullity"] == 1


def test_null_space_direct_mixed_sign_vector():
    # Generic matrix reachable only outside the reactant-positive/product-negative
    # convention: unique null vector (1, 1, -1) with mixed signs.
    matrix = [[Fraction(1), Fraction(2), Fraction(3)]]
    basis = null_space(matrix, 3)
    assert len(basis) == 2  # one row -> nullity 2
    matrix2 = [
        [Fraction(1), Fraction(0), Fraction(1)],
        [Fraction(0), Fraction(1), Fraction(1)],
    ]
    basis2 = null_space(matrix2, 3)
    assert len(basis2) == 1
    assert basis2[0] == [Fraction(-1), Fraction(-1), Fraction(1)]


def test_ordered_elements_first_appearance():
    compounds = [
        C("A", "REACTANT", {"O": 1, "H": 2}),
        C("B", "REACTANT", {"C": 1}),
    ]
    assert ordered_elements(compounds) == ["O", "H", "C"]
    matrix = build_matrix(compounds, ["O", "H", "C"])
    assert matrix[0] == [Fraction(1), Fraction(0)]
    assert matrix[1] == [Fraction(2), Fraction(0)]
    assert matrix[2] == [Fraction(0), Fraction(1)]


def test_review_accepts_certified_coefficients():
    compounds = [
        C("H2", "REACTANT", {"H": 2}),
        C("O2", "REACTANT", {"O": 2}),
        C("H2O", "PRODUCT", {"H": 2, "O": 1}),
    ]
    verdict = review(compounds, {"H2": 2, "O2": 1, "H2O": 2})
    assert verdict["valid"] is True
    assert verdict["reasons"] == []
    assert verdict["gcd"] == 1
    assert verdict["primitive"] is True


def test_review_flags_non_primitive_and_unbalanced_per_element():
    compounds = [
        C("H2", "REACTANT", {"H": 2}),
        C("O2", "REACTANT", {"O": 2}),
        C("H2O", "PRODUCT", {"H": 2, "O": 1}),
    ]
    verdict = review(compounds, {"H2": 4, "O2": 2, "H2O": 4})
    assert verdict["valid"] is False
    assert "NOT_PRIMITIVE" in verdict["reasons"]
    assert verdict["gcd"] == 2
    assert verdict["primitive"] is False
    assert all(row["balanced"] for row in verdict["elements"])

    bad = review(compounds, {"H2": 3, "O2": 1, "H2O": 1})
    assert "NOT_CONSERVED" in bad["reasons"]
    assert set(bad["unbalanced_elements"]) == {"H", "O"}
    rows = {row["element"]: row for row in bad["elements"]}
    assert (rows["H"]["reactant"], rows["H"]["product"]) == (6, 2)
    assert (rows["O"]["reactant"], rows["O"]["product"]) == (2, 1)


def test_review_flags_missing_unknown_and_non_positive():
    compounds = [
        C("A", "REACTANT", {"H": 1}),
        C("B", "PRODUCT", {"H": 1}),
    ]
    verdict = review(compounds, {"A": 1, "X": 3})
    assert verdict["valid"] is False
    assert set(verdict["reasons"]) == {
        "MISSING_COEFFICIENTS",
        "UNKNOWN_COEFFICIENT_IDS",
        "NON_POSITIVE_COEFFICIENT",
        "NOT_CONSERVED",
    }
    assert verdict["missing_ids"] == ["B"]
    assert verdict["unknown_ids"] == ["X"]
    assert verdict["non_positive_ids"] == ["B"]


def test_fractional_gauss_requires_lcm_clearance():
    """Fe3O4 + CO -> Fe + CO2: elimination produces fractions (1/3 etc.)."""
    result = balance([
        C("Fe3O4", "REACTANT", {"Fe": 3, "O": 4}),
        C("CO", "REACTANT", {"C": 1, "O": 1}),
        C("Fe", "PRODUCT", {"Fe": 1}),
        C("CO2", "PRODUCT", {"C": 1, "O": 2}),
    ])
    assert result["status"] == BALANCED
    assert result["coefficients"] == {"Fe3O4": 1, "CO": 4, "Fe": 3, "CO2": 4}


def test_twelve_compounds_with_unique_positive_solution():
    """Upper bound of 12 IDs, 11 independent element rows, nullity exactly 1.

    Six reactants R0..R5 and six products P0..P5. Rows a_i link R_i/P_i
    (weight 1 each). Rows b_j link 2 R_j + R_{j+1} to P_j + 2 P_{j+1}:
    equal side totals (3 == 3), so the all-ones vector balances, while
    the asymmetric weights keep the eleven rows independent.
    """
    symbols = ["H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne", "Na"]
    compositions = [dict() for _ in range(12)]

    def add(row_index: int, compound_index: int, count: int):
        compositions[compound_index][symbols[row_index]] = count

    for i in range(6):
        add(i, i, 1)          # R_i
        add(i, 6 + i, 1)      # P_i
    for j in range(5):
        row = 6 + j
        add(row, j, 2)        # 2 R_j
        add(row, j + 1, 1)    # + R_{j+1}
        add(row, 6 + j, 1)    # P_j
        add(row, 7 + j, 2)    # + 2 P_{j+1}

    compounds = [
        C(f"R{i}", "REACTANT", compositions[i]) for i in range(6)
    ] + [
        C(f"P{i}", "PRODUCT", compositions[6 + i]) for i in range(6)
    ]
    assert len(compounds) == 12
    result = balance(compounds)
    assert result["status"] == BALANCED
    assert result["nullity"] == 1
    assert result["coefficients"] == {
        **{f"R{i}": 1 for i in range(6)},
        **{f"P{i}": 1 for i in range(6)},
    }
    assert len(result["element_totals"]) == 11
    assert all(row["balanced"] for row in result["element_totals"])


def test_all_product_side_still_mathematically_rejected():
    """Semantic validation allows one side empty; the math must reject it:
    a strictly negative matrix row cannot multiply positive vectors to zero."""
    result = balance([
        C("A", "PRODUCT", {"H": 1}),
        C("B", "PRODUCT", {"H": 1}),
    ])
    # Columns are identical negatives -> unique null vector (1, -1): mixed.
    assert result["status"] == NO_POSITIVE_BALANCE
