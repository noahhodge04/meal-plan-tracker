"""student.py + transaction.py against a real in-memory database.

`seeded` provides:
  student 1: set up, 10 swipes, $25 village, $15 campus
  student 2: set up,  5 swipes, $10 village, $0 campus
  student 3: NOT set up
"""
import pytest

import student
import transaction
from models import Notification, Student, Transaction


def notes_for(session, student_id):
    session.expire_all()
    return (session.query(Notification)
            .filter_by(student_id=student_id)
            .order_by(Notification.id)
            .all())


# --------------------------------------------------------------------------
# Transactions
# --------------------------------------------------------------------------
def test_swipe_persists_balance_record_and_notification(seeded, session):
    transaction.create_transaction(student_id=1, type="swipe", amount=1,
                                   location="Dining Hall", note="Lunch")

    balances = student.get_balances(1)
    assert balances["swipes"] == 9
    assert balances["village_flex"] == 25.00
    assert balances["campus_flex"] == 15.00

    history = transaction.get_transactions(1)
    assert len(history) == 1
    assert history[0]["type"] == "swipe"
    assert history[0]["location"] == "Dining Hall"

    notes = notes_for(session, 1)
    assert [n.title for n in notes] == ["Meal-plan transaction recorded"]
    assert notes[0].is_read is False


def test_village_flex_overflow_persists(seeded):
    transaction.create_transaction(student_id=1, type="village_flex", amount=30.00,
                                   location="Market", note="Groceries")

    balances = student.get_balances(1)
    assert balances["village_flex"] == 0.0
    assert balances["campus_flex"] == pytest.approx(10.00)


def test_failed_transaction_changes_nothing(seeded, session):
    with pytest.raises(ValueError):
        transaction.create_transaction(student_id=1, type="campus_flex", amount=999)

    assert student.get_balances(1)["campus_flex"] == 15.00
    assert transaction.get_transactions(1) == []
    assert notes_for(session, 1) == []


def test_transaction_requires_setup(seeded, session):
    with pytest.raises(ValueError, match="initial balance setup"):
        transaction.create_transaction(student_id=3, type="swipe", amount=1)

    assert transaction.get_transactions(3) == []
    assert student.get_balances(3)["swipes"] == 0


def test_history_is_newest_first(seeded):
    transaction.create_transaction(student_id=1, type="swipe", amount=1, location="A", note="first")
    transaction.create_transaction(student_id=1, type="campus_flex", amount=2, location="B", note="second")
    transaction.create_transaction(student_id=1, type="village_flex", amount=3, location="C", note="third")

    assert [t["note"] for t in transaction.get_transactions(1)] == ["third", "second", "first"]


def test_students_are_isolated(seeded):
    transaction.create_transaction(student_id=1, type="swipe", amount=1, location="Hall", note="mine")
    transaction.create_transaction(student_id=2, type="swipe", amount=2, location="Hall", note="theirs")

    assert [t["note"] for t in transaction.get_transactions(1)] == ["mine"]
    assert [t["note"] for t in transaction.get_transactions(2)] == ["theirs"]
    assert student.get_balances(1)["swipes"] == 9
    assert student.get_balances(2)["swipes"] == 3


def test_clear_transactions_only_affects_one_student_and_keeps_balances(seeded):
    transaction.create_transaction(student_id=1, type="swipe", amount=2, location="Hall", note="mine")
    transaction.create_transaction(student_id=2, type="swipe", amount=1, location="Hall", note="theirs")

    transaction.clear_transactions(1)

    assert transaction.get_transactions(1) == []
    assert len(transaction.get_transactions(2)) == 1
    assert student.get_balances(1)["swipes"] == 8       # clearing history doesn't refund


def test_clear_transactions_unknown_student_deletes_nothing(seeded, session):
    transaction.create_transaction(student_id=1, type="swipe", amount=1, location="Hall", note="n")

    with pytest.raises(LookupError):
        transaction.clear_transactions(99)

    assert session.query(Transaction).count() == 1


def test_unknown_student_everywhere(seeded):
    with pytest.raises(LookupError):
        student.get_balances(99)
    with pytest.raises(LookupError):
        transaction.get_transactions(99)
    with pytest.raises(LookupError):
        transaction.create_transaction(student_id=99, type="swipe", amount=1)
    with pytest.raises(LookupError):
        student.set_starting_balances(99, 1, 1.0, 1.0)
    with pytest.raises(LookupError):
        student.reset_swipes_to_starting_balance(99)


# --------------------------------------------------------------------------
# Starting balances
# --------------------------------------------------------------------------
def test_set_starting_balances_persists(seeded, session):
    result = student.set_starting_balances(3, 14, 100, "50.126")

    assert result["setup_completed"] is True
    balances = student.get_balances(3)
    assert balances["swipes"] == balances["starting_swipes"] == 14
    assert balances["village_flex"] == 100.0
    assert balances["campus_flex"] == 50.13
    assert balances["setup_completed"] is True

    assert [n.title for n in notes_for(session, 3)] == ["Starting balances saved"]


def test_starting_balances_cannot_be_changed_after_setup(seeded, session):
    with pytest.raises(ValueError, match="already been configured"):
        student.set_starting_balances(1, 99, 99.0, 99.0)

    balances = student.get_balances(1)
    assert (balances["swipes"], balances["village_flex"], balances["campus_flex"]) == (10, 25.0, 15.0)
    assert notes_for(session, 1) == []


def test_invalid_starting_balances_leave_student_unconfigured(seeded):
    with pytest.raises(ValueError):
        student.set_starting_balances(3, 5, -1.0, 0.0)

    assert student.get_balances(3)["setup_completed"] is False


def test_transactions_work_after_setup(seeded):
    student.set_starting_balances(3, 4, 20.0, 0.0)

    transaction.create_transaction(student_id=3, type="swipe", amount=1)

    assert student.get_balances(3)["swipes"] == 3
    assert student.get_balances(3)["starting_swipes"] == 4


# --------------------------------------------------------------------------
# Swipe reset
# --------------------------------------------------------------------------
def test_reset_swipes_restores_starting_balance(seeded, session):
    transaction.create_transaction(student_id=1, type="swipe", amount=3)

    result = student.reset_swipes_to_starting_balance(1)

    assert result == {"student_id": 1, "previous_swipes": 7, "swipes": 10, "starting_swipes": 10}
    assert student.get_balances(1)["swipes"] == 10

    latest = transaction.get_transactions(1)[0]
    assert latest["type"] == "swipe_reset"
    assert latest["amount"] == 10.0
    assert latest["note"] == "Manual reset from 7 to 10 swipes."

    assert notes_for(session, 1)[-1].title == "Swipes reset"


def test_reset_swipes_does_not_touch_flex_or_other_students(seeded):
    transaction.create_transaction(student_id=1, type="campus_flex", amount=5)
    transaction.create_transaction(student_id=2, type="swipe", amount=2)

    student.reset_swipes_to_starting_balance(1)

    assert student.get_balances(1)["campus_flex"] == 10.0
    assert student.get_balances(2)["swipes"] == 3


def test_reset_swipes_requires_setup(seeded, session):
    with pytest.raises(ValueError, match="Complete initial balance setup"):
        student.reset_swipes_to_starting_balance(3)

    assert transaction.get_transactions(3) == []
    assert notes_for(session, 3) == []


# --------------------------------------------------------------------------
# Cascades through the public API
# --------------------------------------------------------------------------
def test_deleting_student_removes_history_and_notifications(seeded, session):
    transaction.create_transaction(student_id=1, type="swipe", amount=1)

    session.delete(session.get(Student, 1))
    session.commit()

    assert session.query(Transaction).count() == 0
    assert session.query(Notification).count() == 0
