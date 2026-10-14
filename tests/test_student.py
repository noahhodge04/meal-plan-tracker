import re

import pytest
from werkzeug.security import check_password_hash

import student
from models import Notification, Student, Transaction

LOGIN_ID_PATTERN = re.compile(r"MP-[0-9A-F]{8}")


def count_students(session):
    return session.query(Student).count()


def added_of(fake, model):
    return [o for o in fake.added if isinstance(o, model)]


@pytest.fixture
def no_session(monkeypatch):
    """Fails the test if a session is opened (validation must come first)."""
    def boom():
        raise AssertionError("session opened before validation")
    monkeypatch.setattr(student, "get_db_session", boom)


@pytest.fixture
def use_fake(monkeypatch, make_session):
    """Make student.py use a FakeSession holding the given student."""
    def _use(student_obj=None, commit_error=None):
        fake = make_session(student_obj=student_obj, commit_error=commit_error)
        monkeypatch.setattr(student, "get_db_session", lambda: fake)
        return fake
    return _use


# --------------------------------------------------------------------------
# get_db_session
# --------------------------------------------------------------------------
def test_get_db_session(monkeypatch, make_session):
    fake = make_session()
    created = {"tables": False}

    monkeypatch.setattr(
        student.Base.metadata, "create_all",
        lambda engine: created.update({"tables": True}),
    )
    monkeypatch.setattr(student, "SessionLocal", lambda: fake)

    assert student.get_db_session() is fake
    assert created["tables"] is True


# --------------------------------------------------------------------------
# get_student_by_id
# --------------------------------------------------------------------------
def test_get_student_by_id_found(make_session, make_student):
    existing = make_student(id=7)
    assert student.get_student_by_id(make_session(student_obj=existing), 7) is existing


def test_get_student_by_id_missing_raises_lookup_error(make_session, make_student):
    fake = make_session(student_obj=make_student(id=1))

    with pytest.raises(LookupError, match="99"):
        student.get_student_by_id(fake, 99)


# --------------------------------------------------------------------------
# create_student
# --------------------------------------------------------------------------
def test_create_student_success(session):
    result = student.create_student("Alice", "password123")

    assert result["name"] == "Alice"
    assert result["swipes"] == 0
    assert result["village_flex"] == 0.0
    assert result["campus_flex"] == 0.0
    assert result["setup_completed"] is False
    assert LOGIN_ID_PATTERN.fullmatch(result["login_id"])
    assert isinstance(result["student_id"], int)


def test_create_student_starts_unconfigured_in_database(session):
    result = student.create_student("Alice", "password123")

    saved = session.get(Student, result["student_id"])
    assert saved.setup_completed is False
    assert saved.starting_swipes == 0


def test_create_student_does_not_leak_password_data(session):
    result = student.create_student("Alice", "password123")

    assert "password" not in result
    assert "password_hash" not in result
    assert "password123" not in str(result)


def test_create_student_persists_hashed_password(session):
    result = student.create_student("Alice", "password123")

    saved = session.get(Student, result["student_id"])
    assert saved.password_hash != "password123"
    assert check_password_hash(saved.password_hash, "password123")
    assert not check_password_hash(saved.password_hash, "wrong-password")
    assert saved.login_id == result["login_id"]


def test_create_student_strips_name(session):
    assert student.create_student("  Alice  ", "password123")["name"] == "Alice"


def test_create_student_accepts_minimum_length_password(session):
    student.create_student("Alice", "12345678")
    assert count_students(session) == 1


@pytest.mark.parametrize("bad_name", [None, "", "   ", 123])
def test_create_student_rejects_bad_name(session, bad_name):
    with pytest.raises(ValueError, match="name is required"):
        student.create_student(bad_name, "password123")
    assert count_students(session) == 0


@pytest.mark.parametrize("bad_password", [None, "", "short", "1234567", 12345678])
def test_create_student_rejects_bad_password(session, bad_password):
    with pytest.raises(ValueError, match="at least 8 characters"):
        student.create_student("Alice", bad_password)
    assert count_students(session) == 0


def test_create_student_generates_unique_login_ids(session):
    ids = {student.create_student(f"S{i}", "password123")["login_id"] for i in range(10)}
    assert len(ids) == 10


def test_create_student_retries_on_login_id_collision(session, monkeypatch):
    session.add(Student(name="Existing", login_id="MP-AAAAAAAA", password_hash="h"))
    session.commit()

    values = iter(["aaaaaaaa", "bbbbbbbb"])     # first collides, second is free
    monkeypatch.setattr(student.secrets, "token_hex", lambda n: next(values))

    assert student.create_student("Alice", "password123")["login_id"] == "MP-BBBBBBBB"


def test_create_student_gives_up_after_ten_collisions(session, monkeypatch):
    session.add(Student(name="Existing", login_id="MP-AAAAAAAA", password_hash="h"))
    session.commit()
    monkeypatch.setattr(student.secrets, "token_hex", lambda n: "aaaaaaaa")

    with pytest.raises(RuntimeError, match="unique login ID"):
        student.create_student("Alice", "password123")

    assert count_students(session) == 1


def test_create_student_commits_and_closes_session(use_fake):
    fake = use_fake()

    student.create_student("Alice", "password123")

    assert fake.committed is True
    assert fake.closed is True
    assert added_of(fake, Student)[0].name == "Alice"


def test_create_student_rolls_back_and_closes_on_commit_error(use_fake):
    fake = use_fake(commit_error=RuntimeError("disk full"))

    with pytest.raises(RuntimeError, match="disk full"):
        student.create_student("Alice", "password123")

    assert fake.rolled_back is True
    assert fake.closed is True


# --------------------------------------------------------------------------
# get_balances
# --------------------------------------------------------------------------
def test_get_balances(use_fake, make_student):
    fake = use_fake(make_student(login_id="MP-ABCD1234", starting_swipes=12))

    assert student.get_balances(1) == {
        "student_id": 1,
        "login_id": "MP-ABCD1234",
        "name": "Test Student",
        "swipes": 10,
        "starting_swipes": 12,
        "village_flex": 25.00,
        "campus_flex": 15.00,
        "setup_completed": True,
    }
    assert fake.closed is True


def test_get_balances_unknown_student(use_fake, make_student):
    fake = use_fake(make_student(id=1))

    with pytest.raises(LookupError):
        student.get_balances(99)

    assert fake.closed is True


def test_get_balances_closes_session_on_unexpected_error(monkeypatch, use_fake):
    fake = use_fake()

    def raise_error(session, student_id):
        raise RuntimeError("Database error")

    monkeypatch.setattr(student, "get_student_by_id", raise_error)

    with pytest.raises(RuntimeError, match="Database error"):
        student.get_balances(1)

    assert fake.closed is True


# --------------------------------------------------------------------------
# set_starting_balances
# --------------------------------------------------------------------------
def starting(**overrides):
    kwargs = dict(student_id=1, swipes=14, village_flex=100.0, campus_flex=50.0)
    kwargs.update(overrides)
    return kwargs


@pytest.mark.parametrize("bad_swipes", [True, False, 5.0, "5", -1, None])
def test_set_starting_balances_rejects_bad_swipes(no_session, bad_swipes):
    with pytest.raises(ValueError, match="whole number"):
        student.set_starting_balances(**starting(swipes=bad_swipes))


@pytest.mark.parametrize("bad_value", [True, "abc", None, -1, -0.01,
                                       float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("field, label", [("village_flex", "Village Flex"),
                                          ("campus_flex", "Campus Flex")])
def test_set_starting_balances_rejects_bad_money(no_session, field, label, bad_value):
    with pytest.raises(ValueError, match=f"{label} balance must be"):
        student.set_starting_balances(**starting(**{field: bad_value}))


def test_set_starting_balances_success(use_fake, make_student):
    s = make_student(setup_completed=False, swipes=0, starting_swipes=0,
                     village_flex=0.0, campus_flex=0.0)
    fake = use_fake(s)

    result = student.set_starting_balances(1, 14, 100.0, 50.0)

    assert result == {
        "student_id": 1,
        "swipes": 14,
        "starting_swipes": 14,
        "village_flex": 100.0,
        "campus_flex": 50.0,
        "setup_completed": True,
    }
    assert (s.swipes, s.starting_swipes, s.setup_completed) == (14, 14, True)
    assert fake.committed is True
    assert fake.closed is True

    notes = added_of(fake, Notification)
    assert len(notes) == 1
    assert notes[0].title == "Starting balances saved"
    assert notes[0].student_id == 1


def test_set_starting_balances_accepts_numeric_strings_and_rounds_to_cents(use_fake, make_student):
    s = make_student(setup_completed=False)
    use_fake(s)

    result = student.set_starting_balances(1, 0, "100", "10.126")

    assert result["village_flex"] == 100.0
    assert result["campus_flex"] == 10.13
    assert result["swipes"] == 0                 # zero is allowed


def test_set_starting_balances_cannot_be_repeated(use_fake, make_student):
    s = make_student(setup_completed=True, swipes=3, starting_swipes=10)
    fake = use_fake(s)
    before = (s.swipes, s.starting_swipes, s.village_flex, s.campus_flex)

    with pytest.raises(ValueError, match="already been configured"):
        student.set_starting_balances(**starting())

    assert (s.swipes, s.starting_swipes, s.village_flex, s.campus_flex) == before
    assert fake.added == []
    assert fake.rolled_back is True
    assert fake.closed is True


def test_set_starting_balances_unknown_student(use_fake, make_student):
    fake = use_fake(make_student(id=1, setup_completed=False))

    with pytest.raises(LookupError):
        student.set_starting_balances(**starting(student_id=99))

    assert fake.closed is True


def test_set_starting_balances_rolls_back_on_commit_error(use_fake, make_student):
    fake = use_fake(make_student(setup_completed=False), commit_error=RuntimeError("disk full"))

    with pytest.raises(RuntimeError, match="disk full"):
        student.set_starting_balances(**starting())

    assert fake.rolled_back is True
    assert fake.closed is True


# --------------------------------------------------------------------------
# reset_swipes_to_starting_balance
# --------------------------------------------------------------------------
def test_reset_swipes_success(use_fake, make_student):
    s = make_student(swipes=3, starting_swipes=10)
    fake = use_fake(s)

    result = student.reset_swipes_to_starting_balance(1)

    assert result == {"student_id": 1, "previous_swipes": 3,
                      "swipes": 10, "starting_swipes": 10}
    assert s.swipes == 10
    assert fake.committed is True
    assert fake.closed is True


def test_reset_swipes_records_transaction_and_notification(use_fake, make_student):
    fake = use_fake(make_student(swipes=3, starting_swipes=10))

    student.reset_swipes_to_starting_balance(1)

    txns = added_of(fake, Transaction)
    assert len(txns) == 1
    assert txns[0].student_id == 1
    assert txns[0].type == "swipe_reset"
    assert txns[0].amount == 10.0
    assert txns[0].location == ""
    assert txns[0].note == "Manual reset from 3 to 10 swipes."

    notes = added_of(fake, Notification)
    assert len(notes) == 1
    assert notes[0].title == "Swipes reset"
    assert notes[0].message == "Your swipe balance was reset to 10 swipes."


def test_reset_swipes_requires_setup(use_fake, make_student):
    s = make_student(setup_completed=False, swipes=0, starting_swipes=0)
    fake = use_fake(s)

    with pytest.raises(ValueError, match="Complete initial balance setup"):
        student.reset_swipes_to_starting_balance(1)

    assert fake.added == []
    assert fake.committed is False
    assert fake.rolled_back is True
    assert fake.closed is True


def test_reset_swipes_unknown_student(use_fake, make_student):
    fake = use_fake(make_student(id=1))

    with pytest.raises(LookupError):
        student.reset_swipes_to_starting_balance(99)

    assert fake.closed is True


def test_reset_swipes_rolls_back_on_commit_error(use_fake, make_student):
    fake = use_fake(make_student(), commit_error=RuntimeError("disk full"))

    with pytest.raises(RuntimeError, match="disk full"):
        student.reset_swipes_to_starting_balance(1)

    assert fake.rolled_back is True
    assert fake.closed is True


# --------------------------------------------------------------------------
# test_student_preservation
# --------------------------------------------------------------------------

def test_create_student_preserves_existing_student(session):
    session.add(Student(id=1, name="Existing Student", login_id="MP-EXIST01",
                        password_hash="x", swipes=10, village_flex=25.0, campus_flex=15.0))
    session.commit()

    created = student.create_student("Second Student", "safe-password-123")

    session.expire_all()
    existing = session.get(Student, 1)
    assert existing.name == "Existing Student"
    assert (existing.swipes, existing.village_flex, existing.campus_flex) == (10, 25.0, 15.0)
    assert created["student_id"] != 1