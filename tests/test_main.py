"""Flask API tests.

Requires main.py to import from 'student' / 'transaction' (not 'student_class' /
'transaction_class') and to call create_transaction(type=...).
"""
from unittest import mock

import pytest

import main
import transaction


@pytest.fixture
def client():
    main.app.config["TESTING"] = True
    with main.app.test_client() as c:
        yield c


@pytest.fixture
def fake_create(monkeypatch):
    """Autospec'd create_transaction: fails if main calls it with a wrong signature."""
    fake = mock.create_autospec(
        transaction.create_transaction,
        return_value={"status": "success", "swipes": 9,
                      "village_flex": 25.0, "campus_flex": 15.0},
    )
    monkeypatch.setattr(main, "create_transaction", fake)
    return fake


# ---- GET /api/balances ----------------------------------------------------
def test_get_balances_ok(client, monkeypatch):
    data = {"student_id": 1, "name": "Test Student", "swipes": 10,
            "village_flex": 25.0, "campus_flex": 15.0}
    monkeypatch.setattr(main, "get_balances", lambda: data)

    resp = client.get("/api/balances")

    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "data": data}


def test_get_balances_error(client, monkeypatch):
    def boom():
        raise RuntimeError("db down")
    monkeypatch.setattr(main, "get_balances", boom)

    resp = client.get("/api/balances")

    assert resp.status_code == 500
    assert resp.get_json() == {"success": False, "error": "db down"}


# ---- GET /api/transactions ------------------------------------------------
def test_get_transactions_ok(client, monkeypatch):
    history = [{"id": 1, "type": "swipe", "amount": 1.0, "location": "Hall", "note": "n"}]
    monkeypatch.setattr(main, "get_transactions", lambda: history)

    resp = client.get("/api/transactions")

    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "data": history}


def test_get_transactions_error(client, monkeypatch):
    def boom():
        raise RuntimeError("db down")
    monkeypatch.setattr(main, "get_transactions", boom)

    resp = client.get("/api/transactions")

    assert resp.status_code == 500
    assert resp.get_json()["success"] is False


# ---- POST /api/transactions ----------------------------------------------
def test_post_transaction_success(client, fake_create):
    resp = client.post("/api/transactions", data={
        "type": "swipe", "amount": "1", "location": "Dining Hall", "note": "Lunch",
    })

    assert resp.status_code == 201
    assert resp.get_json()["success"] is True
    assert resp.get_json()["data"]["swipes"] == 9
    fake_create.assert_called_once_with(
        type="swipe", amount=1.0, location="Dining Hall", note="Lunch"
    )


def test_post_transaction_missing_optional_fields_become_empty_strings(client, fake_create):
    """None would violate the NOT NULL columns on Transaction."""
    client.post("/api/transactions", data={"type": "swipe", "amount": "1"})

    _, kwargs = fake_create.call_args
    assert kwargs["location"] == ""
    assert kwargs["note"] == ""


def test_post_transaction_non_numeric_amount_is_400(client, fake_create):
    resp = client.post("/api/transactions", data={"type": "swipe", "amount": "abc"})

    assert resp.status_code == 400
    assert resp.get_json()["success"] is False
    fake_create.assert_not_called()


def test_post_transaction_validation_error_is_400(client, fake_create):
    fake_create.side_effect = ValueError("Insufficient Campus Flex balance")

    resp = client.post("/api/transactions", data={"type": "campus_flex", "amount": "999"})

    assert resp.status_code == 400
    assert resp.get_json() == {"success": False, "error": "Insufficient Campus Flex balance"}


def test_post_transaction_unexpected_error_is_500(client, fake_create):
    fake_create.side_effect = RuntimeError("boom")

    resp = client.post("/api/transactions", data={"type": "swipe", "amount": "1"})

    assert resp.status_code == 500
    assert resp.get_json() == {"success": False, "error": "boom"}


def test_post_transaction_end_to_end_with_real_logic(client, db):
    """No mocks: form -> route -> logic -> in-memory DB."""
    from models import Student
    s = db()
    s.add(Student(id=1, name="Test Student", swipes=10, village_flex=25.0, campus_flex=15.0))
    s.commit()
    s.close()

    resp = client.post("/api/transactions", data={
        "type": "village_flex", "amount": "30", "location": "Market", "note": "Food",
    })

    assert resp.status_code == 201
    assert resp.get_json()["data"]["village_flex"] == 0.0
    assert resp.get_json()["data"]["campus_flex"] == pytest.approx(10.0)
