"""Known-case unit tests for ratio-constrained balancing and review."""

from fractions import Fraction

from app.balancer import (
    BALANCED,
    NO_BALANCE,
    NO_POSITIVE_BALANCE,
    UNDERDETERMINED,
    Compound,
    Ratio,
    balance_constrained,
    ratio_rows,
    review_constrained,
)


def C(cid, side, comp):
    return Compound(id=cid, side=side, composition=comp)


def R(a, b, p, q):
    return Ratio(a=a, b=b, a_coefficient=p, b_coefficient=q)


def H2_O2_H2O_H2O2():
    """Classic underdetermined set: nullity 2 without ratios."""
    return [
        C("H2", "REACTANT", {"H": 2}),
        C("O2", "REACTANT", {"O": 2}),
        C("H2O", "PRODUCT", {"H": 2, "O": 1}),
        C("H2O2", "PRODUCT", {"H": 2, "O": 2}),
    ]


def test_ratio_rows_are_exact_constraint_rows():
    rows = ratio_rows(H2_O2_H2O_H2O2(), [R("H2O", "H2O2", 2, 1), R("H2", "O2", 3, 2)])
    # q * c[a] - p * c[b] == 0, columns ordered as the compounds are.
    assert rows == [
        [Fraction(0), Fraction(0), Fraction(1), Fraction(-2)],
        [Fraction(2), Fraction(-3), Fraction(0), Fraction(0)],
    ]


def test_underdetermined_becomes_unique_with_one_ratio():
    result = balance_constrained(H2_O2_H2O_H2O2(), [R("H2O", "H2O2", 2, 1)])
    assert result["status"] == BALANCED
    assert result["nullity"] == 1
    assert result["coefficients"] == {"H2": 3, "O2": 2, "H2O": 2, "H2O2": 1}
    assert result["equation"] == "3 H2 + 2 O2 -> 2 H2O + H2O2"
    # The certified vector honors the approved ratio exactly: 2 : 1.
    assert result["coefficients"]["H2O"] * 1 == result["coefficients"]["H2O2"] * 2
    totals = {row["element"]: row for row in result["element_totals"]}
    assert totals["H"] == {"element": "H", "reactant": 6, "product": 6, "balanced": True}
    assert totals["O"] == {"element": "O", "reactant": 4, "product": 4, "balanced": True}
    # The ratio basis is echoed for the certificate display.
    assert result["ratios"] == [
        {"a": "H2O", "b": "H2O2", "a_coefficient": 2, "b_coefficient": 1}
    ]


def test_two_ratios_pin_down_nullity_three():
    # A -> B + C + D with one element each: nullity 3 without constraints.
    compounds = [
        C("A", "REACTANT", {"H": 1}),
        C("B", "PRODUCT", {"H": 1}),
        C("Cc", "PRODUCT", {"H": 1}),
        C("D", "PRODUCT", {"H": 1}),
    ]
    result = balance_constrained(compounds, [R("B", "Cc", 1, 1), R("Cc", "D", 1, 2)])
    assert result["status"] == BALANCED
    assert result["coefficients"] == {"A": 4, "B": 1, "Cc": 1, "D": 2}
    assert result["ratios"] == [
        {"a": "B", "b": "Cc", "a_coefficient": 1, "b_coefficient": 1},
        {"a": "Cc", "b": "D", "a_coefficient": 1, "b_coefficient": 2},
    ]


def test_contradictory_ratios_report_no_balance():
    compounds = [
        C("A", "REACTANT", {"H": 1}),
        C("B", "PRODUCT", {"H": 1}),
        C("Cc", "PRODUCT", {"H": 1}),
    ]
    result = balance_constrained(compounds, [R("A", "B", 1, 1), R("A", "B", 1, 2)])
    assert result["status"] == NO_BALANCE
    assert result["nullity"] == 0
    assert "contradict" in result["reason"]
    assert len(result["ratios"]) == 2


def test_ratio_can_force_zero_component():
    # c_A = c_B with c_A = c_B + c_C forces c_C = 0.
    compounds = [
        C("A", "REACTANT", {"H": 1}),
        C("B", "PRODUCT", {"H": 1}),
        C("Cc", "PRODUCT", {"H": 1}),
    ]
    result = balance_constrained(compounds, [R("A", "B", 1, 1)])
    assert result["status"] == NO_POSITIVE_BALANCE
    assert result["nullity"] == 1
    assert "zero" in result["reason"]


def test_ratio_can_force_mixed_signs():
    # c_A = c_B with c_A = 2 c_B + c_C forces c_C = -c_A.
    compounds = [
        C("A", "REACTANT", {"H": 1}),
        C("B", "PRODUCT", {"H": 2}),
        C("Cc", "PRODUCT", {"H": 1}),
    ]
    result = balance_constrained(compounds, [R("A", "B", 1, 1)])
    assert result["status"] == NO_POSITIVE_BALANCE
    assert result["nullity"] == 1
    assert "mixes" in result["reason"]


def test_single_ratio_can_leave_system_underdetermined():
    # One ratio on a nullity-3 system: two families remain.
    compounds = [
        C("A", "REACTANT", {"H": 1}),
        C("B", "PRODUCT", {"H": 1}),
        C("Cc", "PRODUCT", {"H": 1}),
        C("D", "PRODUCT", {"H": 1}),
    ]
    result = balance_constrained(compounds, [R("B", "Cc", 1, 1)])
    assert result["status"] == UNDERDETERMINED
    assert result["nullity"] == 2
    assert "still has dimension 2" in result["reason"]


def test_ratio_fractions_clear_to_primitive_integers():
    # 2 c_A = c_B + c_C with c_B : c_C = 2 : 3 -> (5/4, 1, 3/2) -> (5, 4, 6).
    compounds = [
        C("A", "REACTANT", {"H": 2}),
        C("B", "PRODUCT", {"H": 1}),
        C("Cc", "PRODUCT", {"H": 1}),
    ]
    result = balance_constrained(compounds, [R("B", "Cc", 2, 3)])
    assert result["status"] == BALANCED
    assert result["coefficients"] == {"A": 5, "B": 4, "Cc": 6}


def test_non_reduced_ratio_is_accepted_and_normalized_by_elimination():
    # 2:4 constrains exactly like 1:2; the certificate is still primitive.
    halved = balance_constrained(H2_O2_H2O_H2O2(), [R("H2O", "H2O2", 2, 4)])
    assert halved["status"] == BALANCED
    assert halved["coefficients"] == {"H2": 6, "O2": 5, "H2O": 2, "H2O2": 4}

    doubled = balance_constrained(H2_O2_H2O_H2O2(), [R("H2O", "H2O2", 4, 2)])
    assert doubled["status"] == BALANCED
    assert doubled["coefficients"] == {"H2": 3, "O2": 2, "H2O": 2, "H2O2": 1}
    # Echo keeps the approved (unreduced) numbers as the basis.
    assert doubled["ratios"][0]["a_coefficient"] == 4
    assert doubled["ratios"][0]["b_coefficient"] == 2


def test_review_constrained_accepts_certified_recipe():
    verdict = review_constrained(
        H2_O2_H2O_H2O2(),
        {"H2": 3, "O2": 2, "H2O": 2, "H2O2": 1},
        [R("H2O", "H2O2", 2, 1)],
    )
    assert verdict["valid"] is True
    assert verdict["reasons"] == []
    assert verdict["ratios"] == [
        {"a": "H2O", "b": "H2O2", "a_coefficient": 2, "b_coefficient": 1, "satisfied": True}
    ]
    assert verdict["violated_ratios"] == []


def test_review_constrained_flags_conserved_but_ratio_violating_recipe():
    # (4, 3, 2, 2) conserves both elements but has H2O : H2O2 = 1 : 1.
    verdict = review_constrained(
        H2_O2_H2O_H2O2(),
        {"H2": 4, "O2": 3, "H2O": 2, "H2O2": 2},
        [R("H2O", "H2O2", 2, 1)],
    )
    assert verdict["valid"] is False
    assert verdict["reasons"] == ["RATIO_VIOLATED"]
    assert "NOT_CONSERVED" not in verdict["reasons"]
    assert verdict["ratios"][0]["satisfied"] is False
    assert verdict["violated_ratios"] == [0]


def test_review_constrained_combines_base_and_ratio_reasons():
    verdict = review_constrained(
        H2_O2_H2O_H2O2(),
        {"H2": 3, "O2": 1, "H2O": 1, "H2O2": 1},
        [R("H2O", "H2O2", 2, 1)],
    )
    assert verdict["valid"] is False
    assert "NOT_CONSERVED" in verdict["reasons"]
    assert "RATIO_VIOLATED" in verdict["reasons"]
    assert set(verdict["unbalanced_elements"]) == {"H", "O"}


def test_review_constrained_reports_each_ratio_separately():
    compounds = [
        C("A", "REACTANT", {"H": 1}),
        C("B", "PRODUCT", {"H": 1}),
        C("Cc", "PRODUCT", {"H": 1}),
        C("D", "PRODUCT", {"H": 1}),
    ]
    verdict = review_constrained(
        compounds,
        {"A": 4, "B": 1, "Cc": 1, "D": 2},
        [R("B", "Cc", 1, 1), R("Cc", "D", 1, 1)],
    )
    assert verdict["valid"] is False
    assert verdict["reasons"] == ["RATIO_VIOLATED"]
    assert [r["satisfied"] for r in verdict["ratios"]] == [True, False]
    assert verdict["violated_ratios"] == [1]


def test_review_constrained_missing_coefficient_counts_as_zero():
    verdict = review_constrained(
        H2_O2_H2O_H2O2(),
        {"H2": 3, "O2": 2, "H2O": 2},
        [R("H2O", "H2O2", 2, 1)],
    )
    assert verdict["valid"] is False
    assert "MISSING_COEFFICIENTS" in verdict["reasons"]
    assert "RATIO_VIOLATED" in verdict["reasons"]
    assert verdict["missing_ids"] == ["H2O2"]
