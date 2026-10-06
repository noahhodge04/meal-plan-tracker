"""End-to-end tests of student.py + transaction.py against a real (in-memory) DB."""
import pytest

import student
import transaction
from models import Student, Transaction


@pytest.fixture
def seeded(db):
    """Student 1 seeded with keyword args, independent of get_hardcoded_student."""
    s = db()
    s.add(Student(id=1, name="Test Student", swipes=10,
                  village_flex=25.00, campus_flex=15.00))
    s.commit()
    s.close()
    return db


def test_swipe_persists_balance_and_record(seeded):
    transaction.create_transaction("swipe", 1, "Dining Hall", "Lunch")

    assert student.get_balances() == {
        "student_id": 1, "name": "Test Student",
        "swipes": 9, "village_flex": 25.00, "campus_flex": 15.00,
    }
    history = transaction.get_transactions()
    assert len(history) == 1
    assert history[0]["type"] == "swipe"
    assert history[0]["location"] == "Dining Hall"


def test_village_flex_overflow_persists(seeded):
    transaction.create_transaction("village_flex", 30.00, "Market", "Groceries")

    balances = student.get_balances()
    assert balances["village_flex"] == 0.0
    assert balances["campus_flex"] == pytest.approx(10.00)


def test_failed_transaction_changes_nothing(seeded):
    with pytest.raises(ValueError):
        transaction.create_transaction("campus_flex", 999)

    assert student.get_balances()["campus_flex"] == 15.00
    assert transaction.get_transactions() == []


def test_history_is_newest_first(seeded):
    transaction.create_transaction("swipe", 1, "A", "first")
    transaction.create_transaction("campus_flex", 2, "B", "second")
    transaction.create_transaction("village_flex", 3, "C", "third")

    assert [t["note"] for t in transaction.get_transactions()] == ["third", "second", "first"]


def test_clear_transactions_keeps_balances(seeded):
    transaction.create_transaction("swipe", 2, "Hall", "Dinner")

    transaction.clear_transactions()

    assert transaction.get_transactions() == []
    assert student.get_balances()["swipes"] == 8   # clearing history doesn't refund


def test_history_only_includes_hardcoded_student(seeded):
    s = seeded()
    s.add(Student(id=2, name="Other", swipes=1, village_flex=0, campus_flex=0))
    s.add(Transaction(student_id=2, type="swipe", amount=1, location="x", note="other"))
    s.commit()
    s.close()

    transaction.create_transaction("swipe", 1, "Hall", "mine")

    assert [t["note"] for t in transaction.get_transactions()] == ["mine"]
