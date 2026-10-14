"""Unit tests for transaction.py (fake session, no database)."""
import pytest

import transaction
from models import Notification, Transaction


def added_of(fake, model):
    return [o for o in fake.added if isinstance(o, model)]


@pytest.fixture
def setup(monkeypatch, make_student, make_session):
    """Patch transaction.py to use a fake session holding the given student."""
    def _setup(student=None, transactions=None, commit_error=None):
        student = student or make_student()
        fake = make_session(student_obj=student, transactions=transactions,
                            commit_error=commit_error)
        monkeypatch.setattr(transaction, "get_db_session", lambda: fake)
        return student, fake
    return _setup


@pytest.fixture
def no_session(monkeypatch):
    """Fails the test if a session is opened (validation must come first)."""
    def boom():
        raise AssertionError("session opened before validation")
    monkeypatch.setattr(transaction, "get_db_session", boom)


def spend(**overrides):
    kwargs = dict(student_id=1, type="swipe", amount=1)
    kwargs.update(overrides)
    return transaction.create_transaction(**kwargs)


def balances(s):
    return (s.swipes, s.village_flex, s.campus_flex)


# --------------------------------------------------------------------------
# Input validation (all happens before a session is opened)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("bad_type", ["invalidType", "", "SWIPE", "villageFlex",
                                      "campusFlex", "swipe_reset", None])
def test_invalid_type_rejected(no_session, bad_type):
    with pytest.raises(ValueError, match="Invalid transaction type"):
        spend(type=bad_type)


@pytest.mark.parametrize("bad_amount", [None, 0, -1, -5.50, True, False, "abc", "",
                                        float("nan"), float("inf"), float("-inf")])
def test_invalid_amount_rejected(no_session, bad_amount):
    with pytest.raises(ValueError, match="greater than zero"):
        spend(amount=bad_amount)


@pytest.mark.parametrize("bad_amount", [1.5, 0.5, "2.5"])
def test_swipe_amount_must_be_whole_number(no_session, bad_amount):
    with pytest.raises(ValueError, match="whole numbers"):
        spend(type="swipe", amount=bad_amount)


@pytest.mark.parametrize("location", ["x" * 101, None, 5])
def test_invalid_location_rejected(no_session, location):
    with pytest.raises(ValueError, match="Location must be 100 characters or fewer"):
        spend(location=location)


@pytest.mark.parametrize("note", ["x" * 256, None, 5])
def test_invalid_note_rejected(no_session, note):
    with pytest.raises(ValueError, match="Note must be 255 characters or fewer"):
        spend(note=note)


def test_location_and_note_at_limit_are_accepted(setup):
    _, fake = setup()

    spend(location="x" * 100, note="y" * 255)

    assert fake.committed is True


# --------------------------------------------------------------------------
# Student lookup / setup state
# --------------------------------------------------------------------------
def test_unknown_student_raises_lookup_error(setup):
    _, fake = setup()          # only student id=1 exists

    with pytest.raises(LookupError):
        spend(student_id=99)

    assert fake.added == []
    assert fake.committed is False
    assert fake.rolled_back is True
    assert fake.closed is True


def test_requires_setup_before_transactions(setup, make_student):
    student, fake = setup(make_student(setup_completed=False))
    before = balances(student)

    with pytest.raises(ValueError, match="initial balance setup"):
        spend()

    assert balances(student) == before
    assert fake.added == []
    assert fake.committed is False
    assert fake.rolled_back is True
    assert fake.closed is True


# --------------------------------------------------------------------------
# Swipes
# --------------------------------------------------------------------------
def test_swipe_success(setup, make_student):
    student, fake = setup(make_student(swipes=10))

    result = spend(type="swipe", amount=1, location="Dining Hall", note="Lunch")

    assert result == {"status": "success", "swipes": 9,
                      "village_flex": 25.00, "campus_flex": 15.00}
    assert student.swipes == 9

    txns = added_of(fake, Transaction)
    assert len(txns) == 1
    assert txns[0].type == "swipe"
    assert txns[0].amount == 1.0
    assert txns[0].location == "Dining Hall"
    assert txns[0].note == "Lunch"
    assert txns[0].student_id == student.id

    assert fake.committed is True
    assert fake.closed is True


def test_swipe_accepts_whole_number_float_and_numeric_string(setup, make_student):
    student, fake = setup(make_student(swipes=10))

    spend(type="swipe", amount=2.0)
    spend(type="swipe", amount="3")

    assert student.swipes == 5
    assert [t.amount for t in added_of(fake, Transaction)] == [2.0, 3.0]


def test_swipe_can_use_last_swipe(setup, make_student):
    setup(make_student(swipes=1))
    assert spend(type="swipe", amount=1)["swipes"] == 0


def test_swipe_insufficient(setup, make_student):
    student, fake = setup(make_student(swipes=0))

    with pytest.raises(ValueError, match="Insufficient swipes available"):
        spend(type="swipe", amount=1)

    assert student.swipes == 0
    assert fake.added == []
    assert fake.committed is False
    assert fake.rolled_back is True
    assert fake.closed is True


def test_defaults_for_location_and_note(setup):
    _, fake = setup()

    spend()

    txn = added_of(fake, Transaction)[0]
    assert txn.location == ""
    assert txn.note == ""


def test_location_and_note_are_trimmed(setup):
    _, fake = setup()

    spend(location="  Dining Hall  ", note="  Lunch  ")

    txn = added_of(fake, Transaction)[0]
    assert txn.location == "Dining Hall"
    assert txn.note == "Lunch"


# --------------------------------------------------------------------------
# Campus Flex
# --------------------------------------------------------------------------
def test_campus_flex_success(setup, make_student):
    setup(make_student(campus_flex=15.00))

    result = spend(type="campus_flex", amount=4.50, location="Campus Store", note="Supplies")

    assert result["campus_flex"] == pytest.approx(10.50)
    assert result["village_flex"] == 25.00      # untouched
    assert result["swipes"] == 10               # untouched


def test_campus_flex_exact_balance(setup, make_student):
    student, _ = setup(make_student(campus_flex=15.00))
    spend(type="campus_flex", amount=15.00)
    assert student.campus_flex == 0


def test_campus_flex_result_is_rounded_to_cents(setup, make_student):
    student, _ = setup(make_student(campus_flex=10.10))
    spend(type="campus_flex", amount=0.10)
    assert student.campus_flex == 10.0          # not 9.999999999999998


def test_campus_flex_insufficient(setup, make_student):
    student, fake = setup(make_student(campus_flex=5.00))

    with pytest.raises(ValueError, match="Insufficient Campus Flex"):
        spend(type="campus_flex", amount=5.01)

    assert student.campus_flex == 5.00
    assert fake.added == []
    assert fake.rolled_back is True


# --------------------------------------------------------------------------
# Village Flex (spills into Campus Flex once Village is empty)
# --------------------------------------------------------------------------
def test_village_flex_within_village_balance(setup, make_student):
    student, _ = setup(make_student(village_flex=25.00, campus_flex=15.00))

    spend(type="village_flex", amount=10.00)

    assert student.village_flex == pytest.approx(15.00)
    assert student.campus_flex == 15.00


def test_village_flex_exact_village_balance(setup, make_student):
    student, _ = setup(make_student(village_flex=25.00, campus_flex=15.00))

    spend(type="village_flex", amount=25.00)

    assert student.village_flex == 0
    assert student.campus_flex == 15.00


def test_village_flex_overflows_into_campus(setup, make_student):
    _, fake = setup(make_student(village_flex=25.00, campus_flex=15.00))

    result = spend(type="village_flex", amount=30.00)

    assert result["village_flex"] == 0.0
    assert result["campus_flex"] == pytest.approx(10.00)
    assert added_of(fake, Transaction)[0].amount == 30.00   # full amount recorded
    assert fake.committed is True


def test_village_flex_uses_entire_combined_balance(setup, make_student):
    student, _ = setup(make_student(village_flex=25.00, campus_flex=15.00))

    spend(type="village_flex", amount=40.00)

    assert student.village_flex == 0
    assert student.campus_flex == pytest.approx(0)


def test_village_flex_with_empty_village_comes_entirely_from_campus(setup, make_student):
    student, _ = setup(make_student(village_flex=0.0, campus_flex=15.00))

    spend(type="village_flex", amount=5.00)

    assert student.village_flex == 0
    assert student.campus_flex == pytest.approx(10.00)


def test_village_flex_insufficient_combined_balance(setup, make_student):
    student, fake = setup(make_student(village_flex=25.00, campus_flex=15.00))
    before = balances(student)

    with pytest.raises(ValueError, match="Insufficient total Flex"):
        spend(type="village_flex", amount=40.01)

    assert balances(student) == before
    assert fake.added == []
    assert fake.rolled_back is True
    assert fake.closed is True


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------
@pytest.mark.parametrize("type_, amount, expected", [
    ("swipe", 1, "A swipe transaction for 1 was recorded."),
    ("campus_flex", 4.5, "A campus flex transaction for 4.5 was recorded."),
    ("village_flex", 30, "A village flex transaction for 30 was recorded."),
])
def test_successful_transaction_creates_notification(setup, type_, amount, expected):
    _, fake = setup()

    spend(type=type_, amount=amount)

    notes = added_of(fake, Notification)
    assert len(notes) == 1
    assert notes[0].student_id == 1
    assert notes[0].title == "Meal-plan transaction recorded"
    assert notes[0].message == expected


def test_failed_transaction_creates_no_notification(setup, make_student):
    _, fake = setup(make_student(swipes=0))

    with pytest.raises(ValueError):
        spend(type="swipe", amount=1)

    assert added_of(fake, Notification) == []


# --------------------------------------------------------------------------
# Session handling
# --------------------------------------------------------------------------
def test_rollback_and_close_when_commit_fails(setup):
    _, fake = setup(commit_error=RuntimeError("disk full"))

    with pytest.raises(RuntimeError, match="disk full"):
        spend()

    assert fake.rolled_back is True
    assert fake.closed is True


def test_get_db_session(monkeypatch, make_session):
    fake = make_session()
    monkeypatch.setattr(transaction, "SessionLocal", lambda: fake)

    assert transaction.get_db_session() is fake


# --------------------------------------------------------------------------
# get_transactions
# --------------------------------------------------------------------------
def test_get_transactions_maps_fields_and_filters_by_student(setup, make_txn):
    rows = [
        make_txn(2, type="campus_flex", amount=5.0, location="Store", note="Pens"),
        make_txn(3, student_id=2, note="someone else"),
        make_txn(1),
    ]
    _, fake = setup(transactions=rows)

    result = transaction.get_transactions(1)

    assert result == [
        {"id": 2, "type": "campus_flex", "amount": 5.0, "location": "Store", "note": "Pens"},
        {"id": 1, "type": "swipe", "amount": 1.0, "location": "Hall", "note": "n"},
    ]
    assert fake.closed is True


def test_get_transactions_empty(setup):
    _, fake = setup(transactions=[])
    assert transaction.get_transactions(1) == []
    assert fake.closed is True


def test_get_transactions_unknown_student(setup, make_txn):
    _, fake = setup(transactions=[make_txn(1)])

    with pytest.raises(LookupError):
        transaction.get_transactions(99)

    assert fake.closed is True


# --------------------------------------------------------------------------
# clear_transactions
# --------------------------------------------------------------------------
def test_clear_transactions_only_deletes_that_students_rows(setup, make_txn):
    rows = [make_txn(1, student_id=1), make_txn(2, student_id=2), make_txn(3, student_id=1)]
    _, fake = setup(transactions=rows)

    transaction.clear_transactions(1)

    assert [t.id for t in fake.transactions] == [2]     # student 2's row survives
    assert fake.committed is True
    assert fake.closed is True


def test_clear_transactions_unknown_student_deletes_nothing(setup, make_txn):
    _, fake = setup(transactions=[make_txn(1)])

    with pytest.raises(LookupError):
        transaction.clear_transactions(99)

    assert fake.delete_called is False
    assert len(fake.transactions) == 1
    assert fake.committed is False
    assert fake.rolled_back is True
    assert fake.closed is True
