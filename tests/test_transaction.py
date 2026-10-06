import pytest
from types import SimpleNamespace

import transaction
from conftest import FakeSession, make_student


@pytest.fixture
def setup(monkeypatch):
    """Patch transaction.py to use a fake session and a given student."""
    def _setup(student=None, transactions=None, commit_error=None):
        student = student or make_student()
        session = FakeSession(student_obj=student, transactions=transactions,
                              commit_error=commit_error)
        monkeypatch.setattr(transaction, "get_db_session", lambda: session)
        monkeypatch.setattr(transaction, "get_hardcoded_student", lambda _: student)
        return student, session
    return _setup


def balances(student):
    return (student.swipes, student.village_flex, student.campus_flex)


# --------------------------------------------------------------------------
# Validation (must happen before any session is opened)
# --------------------------------------------------------------------------
@pytest.fixture
def no_session(monkeypatch):
    def boom():
        raise AssertionError("session opened before validation")
    monkeypatch.setattr(transaction, "get_db_session", boom)


@pytest.mark.parametrize("bad_type", ["invalidType", "", "SWIPE", "villageFlex", "campusFlex", None])
def test_invalid_type_rejected(no_session, bad_type):
    with pytest.raises(ValueError, match="Invalid transaction type"):
        transaction.create_transaction(bad_type, 1, "Location", "Note")


@pytest.mark.parametrize("amount", [None, 0, -1, -5.50])
def test_invalid_amount_rejected(no_session, amount):
    with pytest.raises(ValueError, match="greater than zero"):
        transaction.create_transaction("swipe", amount)


# --------------------------------------------------------------------------
# Swipes
# --------------------------------------------------------------------------
def test_swipe_success(setup):
    student, session = setup(make_student(swipes=10))

    result = transaction.create_transaction("swipe", 1, "Dining Hall", "Lunch")

    assert result == {"status": "success", "swipes": 9,
                      "village_flex": 25.00, "campus_flex": 15.00}
    assert student.swipes == 9

    assert len(session.added) == 1
    txn = session.added[0]
    assert txn.type == "swipe"
    assert txn.amount == 1.0
    assert txn.location == "Dining Hall"
    assert txn.note == "Lunch"
    assert txn.student_id == student.id

    assert session.committed is True
    assert session.closed is True


def test_swipe_can_use_last_swipe(setup):
    student, _ = setup(make_student(swipes=1))
    result = transaction.create_transaction("swipe", 1)
    assert result["swipes"] == 0


def test_swipe_insufficient(setup):
    student, session = setup(make_student(swipes=0))

    with pytest.raises(ValueError, match="swipes available"):
        transaction.create_transaction("swipe", 1)

    assert student.swipes == 0
    assert session.added == []
    assert session.committed is False
    assert session.rolled_back is True
    assert session.closed is True


def test_defaults_for_location_and_note(setup):
    _, session = setup()
    transaction.create_transaction("swipe", 1)
    assert session.added[0].location == ""
    assert session.added[0].note == ""


# --------------------------------------------------------------------------
# Campus Flex
# --------------------------------------------------------------------------
def test_campus_flex_success(setup):
    student, session = setup(make_student(campus_flex=15.00))

    result = transaction.create_transaction("campus_flex", 4.50, "Campus Store", "Supplies")

    assert result["campus_flex"] == pytest.approx(10.50)
    assert result["village_flex"] == 25.00      # untouched
    assert result["swipes"] == 10               # untouched
    assert session.added[0].amount == 4.50
    assert session.committed is True


def test_campus_flex_exact_balance(setup):
    student, _ = setup(make_student(campus_flex=15.00))
    transaction.create_transaction("campus_flex", 15.00)
    assert student.campus_flex == 0


def test_campus_flex_insufficient(setup):
    student, session = setup(make_student(campus_flex=5.00))

    with pytest.raises(ValueError, match="Insufficient Campus Flex"):
        transaction.create_transaction("campus_flex", 5.01)

    assert student.campus_flex == 5.00
    assert session.added == []
    assert session.rolled_back is True


# --------------------------------------------------------------------------
# Village Flex (spills into Campus Flex once Village is empty)
# --------------------------------------------------------------------------
def test_village_flex_within_village_balance(setup):
    student, _ = setup(make_student(village_flex=25.00, campus_flex=15.00))

    transaction.create_transaction("village_flex", 10.00)

    assert student.village_flex == pytest.approx(15.00)
    assert student.campus_flex == 15.00


def test_village_flex_exact_village_balance(setup):
    student, _ = setup(make_student(village_flex=25.00, campus_flex=15.00))

    transaction.create_transaction("village_flex", 25.00)

    assert student.village_flex == 0
    assert student.campus_flex == 15.00


def test_village_flex_overflows_into_campus(setup):
    student, session = setup(make_student(village_flex=25.00, campus_flex=15.00))

    result = transaction.create_transaction("village_flex", 30.00)

    assert result["village_flex"] == 0.0
    assert result["campus_flex"] == pytest.approx(10.00)
    assert session.added[0].amount == 30.00  # full amount recorded
    assert session.committed is True


def test_village_flex_uses_entire_combined_balance(setup):
    student, _ = setup(make_student(village_flex=25.00, campus_flex=15.00))

    transaction.create_transaction("village_flex", 40.00)

    assert student.village_flex == 0
    assert student.campus_flex == pytest.approx(0)


def test_village_flex_insufficient_combined_balance(setup):
    student, session = setup(make_student(village_flex=25.00, campus_flex=15.00))
    before = balances(student)

    with pytest.raises(ValueError, match="Insufficient total Flex"):
        transaction.create_transaction("village_flex", 40.01)

    assert balances(student) == before
    assert session.added == []
    assert session.rolled_back is True
    assert session.closed is True


# --------------------------------------------------------------------------
# Session handling
# --------------------------------------------------------------------------
def test_rollback_and_close_when_commit_fails(setup):
    _, session = setup(commit_error=RuntimeError("disk full"))

    with pytest.raises(RuntimeError, match="disk full"):
        transaction.create_transaction("swipe", 1)

    assert session.rolled_back is True
    assert session.closed is True


def test_get_db_session(monkeypatch):
    session = FakeSession()
    created = {"tables": False}

    monkeypatch.setattr(
        transaction.Base.metadata, "create_all",
        lambda engine: created.update({"tables": True}),
    )
    monkeypatch.setattr(transaction, "SessionLocal", lambda: session)

    assert transaction.get_db_session() is session
    assert created["tables"] is True


# --------------------------------------------------------------------------
# get_transactions / clear_transactions
# --------------------------------------------------------------------------
def make_txn(id, student_id=1, type="swipe", amount=1.0, location="Hall", note="n"):
    return SimpleNamespace(id=id, student_id=student_id, type=type,
                           amount=amount, location=location, note=note)


def test_get_transactions_maps_fields_and_filters_by_student(setup):
    rows = [
        make_txn(2, type="campus_flex", amount=5.0, location="Store", note="Pens"),
        make_txn(3, student_id=2, note="someone else"),
        make_txn(1),
    ]
    _, session = setup(transactions=rows)

    result = transaction.get_transactions()

    assert result == [
        {"id": 2, "type": "campus_flex", "amount": 5.0, "location": "Store", "note": "Pens"},
        {"id": 1, "type": "swipe", "amount": 1.0, "location": "Hall", "note": "n"},
    ]
    assert session.closed is True


def test_get_transactions_empty(setup):
    _, session = setup(transactions=[])
    assert transaction.get_transactions() == []
    assert session.closed is True


def test_clear_transactions(setup):
    _, session = setup()

    transaction.clear_transactions()

    assert session.delete_called is True
    assert session.committed is True
    assert session.closed is True
