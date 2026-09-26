"""End-to-end HTTP tests for the ratio-constrained endpoints.

The original /api/balance and /api/review contracts are covered by
test_api.py and stay untouched; these cover /api/balance/constrained and
/api/review/constrained only.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def UNDERDETERMINED_REQUEST():
    return {
        "compounds": [
            {"id": "H2", "side": "REACTANT", "composition": {"H": 2}},
            {"id": "O2", "side": "REACTANT", "composition": {"O": 2}},
            {"id": "H2O", "side": "PRODUCT", "composition": {"H": 2, "O": 1}},
            {"id": "H2O2", "side": "PRODUCT", "composition": {"H": 2, "O": 2}},
        ]
    }


def RATIO():
    return {"a": "H2O", "b": "H2O2", "a_coefficient": 2, "b_coefficient": 1}


def constrained_payload(**overrides):
    payload = UNDERDETERMINED_REQUEST()
    payload["ratios"] = [RATIO()]
    payload.update(overrides)
    return payload


def test_constrained_balance_turns_multi_solution_into_unique_certificate():
    plain = client.post("/api/balance", json=UNDERDETERMINED_REQUEST()).json()
    assert plain["status"] == "UNDERDETERMINED"
    assert "ratios" not in plain  # original response shape unchanged

    response = client.post("/api/balance/constrained", json=constrained_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "BALANCED"
    assert body["nullity"] == 1
    assert body["coefficients"] == {"H2": 3, "O2": 2, "H2O": 2, "H2O2": 1}
    assert body["equation"] == "3 H2 + 2 O2 -> 2 H2O + H2O2"
    assert body["ratios"] == [RATIO()]
    assert all(row["balanced"] for row in body["element_totals"])


def test_constrained_balance_statuses_for_each_failure_mode():
    # Contradictory ratios -> NO_BALANCE.
    payload = constrained_payload(
        ratios=[RATIO(), {"a": "H2O", "b": "H2O2", "a_coefficient": 1, "b_coefficient": 1}]
    )
    body = client.post("/api/balance/constrained", json=payload).json()
    assert body["status"] == "NO_BALANCE"
    assert body["nullity"] == 0
    assert len(body["ratios"]) == 2

    # One ratio on a nullity-3 system -> still UNDERDETERMINED.
    payload = {
        "compounds": [
            {"id": "A", "side": "REACTANT", "composition": {"H": 1}},
            {"id": "B", "side": "PRODUCT", "composition": {"H": 1}},
            {"id": "C", "side": "PRODUCT", "composition": {"H": 1}},
            {"id": "D", "side": "PRODUCT", "composition": {"H": 1}},
        ],
        "ratios": [{"a": "B", "b": "C", "a_coefficient": 1, "b_coefficient": 1}],
    }
    body = client.post("/api/balance/constrained", json=payload).json()
    assert body["status"] == "UNDERDETERMINED"
    assert body["nullity"] == 2

    # Unique constrained vector with a zero component -> NO_POSITIVE_BALANCE.
    payload = {
        "compounds": [
            {"id": "A", "side": "REACTANT", "composition": {"H": 1}},
            {"id": "B", "side": "PRODUCT", "composition": {"H": 1}},
            {"id": "C", "side": "PRODUCT", "composition": {"H": 1}},
        ],
        "ratios": [{"a": "A", "b": "B", "a_coefficient": 1, "b_coefficient": 1}],
    }
    body = client.post("/api/balance/constrained", json=payload).json()
    assert body["status"] == "NO_POSITIVE_BALANCE"
    assert body["nullity"] == 1


def test_constrained_balance_rejects_bad_ratio_count():
    for ratios in ([], [RATIO(), RATIO(), RATIO()]):
        response = client.post(
            "/api/balance/constrained", json=constrained_payload(ratios=ratios)
        )
        assert response.status_code == 422
        assert response.json()["issues"][0]["code"] == "INVALID_RATIO_COUNT"


def test_constrained_balance_rejects_semantic_ratio_errors():
    # Same compound on both ends.
    response = client.post(
        "/api/balance/constrained",
        json=constrained_payload(
            ratios=[{"a": "H2O", "b": "H2O", "a_coefficient": 1, "b_coefficient": 1}]
        ),
    )
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "RATIO_SAME_COMPOUND"

    # Unknown compound reference.
    response = client.post(
        "/api/balance/constrained",
        json=constrained_payload(
            ratios=[{"a": "H2O", "b": "NaCl", "a_coefficient": 1, "b_coefficient": 1}]
        ),
    )
    assert response.status_code == 422
    issue = response.json()["issues"][0]
    assert issue["code"] == "UNKNOWN_RATIO_COMPOUND"
    assert issue["compound_id"] == "NaCl"

    # Empty reference.
    response = client.post(
        "/api/balance/constrained",
        json=constrained_payload(
            ratios=[{"a": "", "b": "H2O", "a_coefficient": 1, "b_coefficient": 1}]
        ),
    )
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "EMPTY_RATIO_COMPOUND"

    # Non-positive ratio coefficient.
    response = client.post(
        "/api/balance/constrained",
        json=constrained_payload(
            ratios=[{"a": "H2O", "b": "H2O2", "a_coefficient": 0, "b_coefficient": 1}]
        ),
    )
    assert response.status_code == 422
    issue = response.json()["issues"][0]
    assert issue["code"] == "NON_POSITIVE_RATIO"
    assert issue["loc"] == "ratios[0].a_coefficient"


def test_constrained_balance_rejects_structural_ratio_errors():
    # Float coefficient.
    response = client.post(
        "/api/balance/constrained",
        json=constrained_payload(
            ratios=[{"a": "H2O", "b": "H2O2", "a_coefficient": 1.5, "b_coefficient": 1}]
        ),
    )
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "INVALID_INTEGER"

    # Boolean coefficient must not coerce to 1.
    response = client.post(
        "/api/balance/constrained",
        json=constrained_payload(
            ratios=[{"a": "H2O", "b": "H2O2", "a_coefficient": True, "b_coefficient": 1}]
        ),
    )
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "INVALID_INTEGER"

    # Unknown field inside a ratio and at the top level.
    bad = RATIO()
    bad["note"] = "approved by management"
    response = client.post("/api/balance/constrained", json=constrained_payload(ratios=[bad]))
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "UNKNOWN_FIELD"

    payload = constrained_payload()
    payload["comment"] = "rush order"
    response = client.post("/api/balance/constrained", json=payload)
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "UNKNOWN_FIELD"


def test_constrained_balance_still_validates_compounds():
    payload = constrained_payload()
    payload["compounds"][0]["composition"] = {}
    response = client.post("/api/balance/constrained", json=payload)
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "EMPTY_COMPOSITION"


def test_constrained_review_checks_ratios():
    # Certified recipe passes conservation and the ratio.
    payload = constrained_payload(
        coefficients={"H2": 3, "O2": 2, "H2O": 2, "H2O2": 1}
    )
    response = client.post("/api/review/constrained", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["reasons"] == []
    assert body["ratios"] == [{**RATIO(), "satisfied": True}]
    assert body["violated_ratios"] == []

    # (4, 3, 2, 2) conserves every element but violates the approved 2:1 ratio.
    payload["coefficients"] = {"H2": 4, "O2": 3, "H2O": 2, "H2O2": 2}
    body = client.post("/api/review/constrained", json=payload).json()
    assert body["valid"] is False
    assert body["reasons"] == ["RATIO_VIOLATED"]
    assert body["unbalanced_elements"] == []
    assert body["ratios"][0]["satisfied"] is False
    assert body["violated_ratios"] == [0]


def test_constrained_review_rejects_bad_ratios_and_compounds():
    payload = constrained_payload(coefficients={"H2": 3, "O2": 2, "H2O": 2, "H2O2": 1})
    payload["ratios"] = []
    response = client.post("/api/review/constrained", json=payload)
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "INVALID_RATIO_COUNT"

    payload = constrained_payload(coefficients={"H2": 3, "O2": 2, "H2O": 2, "H2O2": 1})
    payload["compounds"][1]["id"] = "H2"  # duplicate id
    response = client.post("/api/review/constrained", json=payload)
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "DUPLICATE_ID"


def test_original_endpoints_ignore_nothing_and_stay_unchanged():
    # The ratio-free endpoints keep their exact previous behaviour: unknown
    # fields (including "ratios") are rejected there.
    payload = UNDERDETERMINED_REQUEST()
    payload["ratios"] = [RATIO()]
    response = client.post("/api/balance", json=payload)
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "UNKNOWN_FIELD"

    review_payload = UNDERDETERMINED_REQUEST()
    review_payload["coefficients"] = {"H2": 3, "O2": 2, "H2O": 2, "H2O2": 1}
    review_payload["ratios"] = [RATIO()]
    response = client.post("/api/review", json=review_payload)
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "UNKNOWN_FIELD"
