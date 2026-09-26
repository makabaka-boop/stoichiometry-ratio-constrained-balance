"""End-to-end HTTP tests against the FastAPI app."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def H2O2_REQUEST():
    return {
        "compounds": [
            {"id": "H2", "side": "REACTANT", "composition": {"H": 2}},
            {"id": "O2", "side": "REACTANT", "composition": {"O": 2}},
            {"id": "H2O", "side": "PRODUCT", "composition": {"H": 2, "O": 1}},
        ]
    }


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_balance_water():
    response = client.post("/api/balance", json=H2O2_REQUEST())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "BALANCED"
    assert body["coefficients"] == {"H2": 2, "O2": 1, "H2O": 2}
    assert body["equation"] == "2 H2 + O2 -> 2 H2O"
    assert all(row["balanced"] for row in body["element_totals"])


def test_balance_no_balance():
    response = client.post(
        "/api/balance",
        json={
            "compounds": [
                {"id": "A", "side": "REACTANT", "composition": {"H": 1}},
                {"id": "B", "side": "PRODUCT", "composition": {"O": 1}},
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "NO_BALANCE"


def test_balance_underdetermined():
    response = client.post(
        "/api/balance",
        json={
            "compounds": [
                {"id": "A", "side": "REACTANT", "composition": {"H": 1}},
                {"id": "B", "side": "PRODUCT", "composition": {"H": 1}},
                {"id": "C", "side": "PRODUCT", "composition": {"H": 1}},
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "UNDERDETERMINED"
    assert body["nullity"] == 2


def test_balance_no_positive_balance():
    response = client.post(
        "/api/balance",
        json={
            "compounds": [
                {"id": "A", "side": "REACTANT", "composition": {"H": 1}},
                {"id": "B", "side": "REACTANT", "composition": {"O": 1}},
                {"id": "C", "side": "PRODUCT", "composition": {"H": 1}},
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "NO_POSITIVE_BALANCE"


def test_reject_unknown_field():
    payload = H2O2_REQUEST()
    payload["compounds"][0]["mystery"] = 1
    response = client.post("/api/balance", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "VALIDATION_FAILED"
    codes = {issue["code"] for issue in body["issues"]}
    assert "UNKNOWN_FIELD" in codes
    locs = {issue["loc"] for issue in body["issues"]}
    assert any(loc.startswith("compounds.0") for loc in locs)


def test_reject_duplicate_ids():
    payload = H2O2_REQUEST()
    payload["compounds"][2]["id"] = "H2"
    response = client.post("/api/balance", json=payload)
    assert response.status_code == 422
    codes = {issue["code"] for issue in response.json()["issues"]}
    assert codes == {"DUPLICATE_ID"}


def test_reject_illegal_element_symbol():
    payload = H2O2_REQUEST()
    payload["compounds"][0]["composition"] = {"Xx": 2}
    response = client.post("/api/balance", json=payload)
    assert response.status_code == 422
    issue = response.json()["issues"][0]
    assert issue["code"] == "INVALID_ELEMENT"
    assert issue["element"] == "Xx"


def test_reject_empty_composition():
    payload = H2O2_REQUEST()
    payload["compounds"][0]["composition"] = {}
    response = client.post("/api/balance", json=payload)
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "EMPTY_COMPOSITION"


def test_reject_non_positive_count_and_float():
    payload = H2O2_REQUEST()
    payload["compounds"][0]["composition"] = {"H": 0}
    response = client.post("/api/balance", json=payload)
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "NON_POSITIVE_COUNT"

    payload2 = H2O2_REQUEST()
    payload2["compounds"][0]["composition"] = {"H": 2.5}
    response2 = client.post("/api/balance", json=payload2)
    assert response2.status_code == 422
    assert response2.json()["issues"][0]["code"] == "INVALID_INTEGER"

    # Booleans must not sneak through as 0/1 (bool is an int subclass).
    payload3 = H2O2_REQUEST()
    payload3["compounds"][0]["composition"] = {"H": True}
    response3 = client.post("/api/balance", json=payload3)
    assert response3.status_code == 422
    assert response3.json()["issues"][0]["code"] == "INVALID_INTEGER"


def test_reject_bad_side_empty_id_and_bad_count_range():
    payload = H2O2_REQUEST()
    payload["compounds"][0]["side"] = "CATALYST"
    response = client.post("/api/balance", json=payload)
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "INVALID_SIDE"

    only_one = {"compounds": H2O2_REQUEST()["compounds"][:1]}
    response = client.post("/api/balance", json=only_one)
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "INVALID_COMPOUND_COUNT"

    payload = H2O2_REQUEST()
    payload["compounds"][0]["id"] = ""
    response = client.post("/api/balance", json=payload)
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "EMPTY_ID"


def test_reject_too_many_elements():
    symbols = ["H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
               "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca", "Sc"]
    payload = {
        "compounds": [
            {"id": "A", "side": "REACTANT", "composition": {s: 1 for s in symbols}},
            {"id": "B", "side": "PRODUCT", "composition": {s: 1 for s in symbols}},
        ]
    }
    response = client.post("/api/balance", json=payload)
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "TOO_MANY_ELEMENTS"


def test_reject_malformed_json_body():
    response = client.post(
        "/api/balance",
        content=b"{not json",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "REQUEST_MALFORMED"


def test_reject_too_many_compounds():
    thirteen = {
        "compounds": [
            {"id": f"C{i}", "side": "REACTANT" if i % 2 == 0 else "PRODUCT",
             "composition": {"H": 1}}
            for i in range(13)
        ]
    }
    response = client.post("/api/balance", json=thirteen)
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "INVALID_COMPOUND_COUNT"


def test_accepts_exactly_twenty_elements():
    symbols = ["H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
               "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca"]
    payload = {
        "compounds": [
            {"id": "A", "side": "REACTANT", "composition": {s: 1 for s in symbols}},
            {"id": "B", "side": "PRODUCT", "composition": {s: 1 for s in symbols}},
        ]
    }
    response = client.post("/api/balance", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "BALANCED"
    assert body["coefficients"] == {"A": 1, "B": 1}
    assert len(body["element_totals"]) == 20


def test_review_endpoint_accepts_and_rejects():
    payload = H2O2_REQUEST()
    payload["coefficients"] = {"H2": 2, "O2": 1, "H2O": 2}
    response = client.post("/api/review", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["reasons"] == []

    payload["coefficients"] = {"H2": 4, "O2": 2, "H2O": 3}
    response = client.post("/api/review", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert "NOT_CONSERVED" in body["reasons"]
    # H: 8 vs 6, O: 4 vs 3 — every element is off.
    assert set(body["unbalanced_elements"]) == {"H", "O"}

    # Only oxygen off, hydrogen conserved: (1, 2, 1) -> H 2=2, O 4 vs 1.
    payload["coefficients"] = {"H2": 1, "O2": 2, "H2O": 1}
    body = client.post("/api/review", json=payload).json()
    assert body["unbalanced_elements"] == ["O"]

    # Semantic issues in the compound set still 422 the review call.
    payload["compounds"][0]["composition"] = {}
    response = client.post("/api/review", json=payload)
    assert response.status_code == 422
    assert response.json()["issues"][0]["code"] == "EMPTY_COMPOSITION"
