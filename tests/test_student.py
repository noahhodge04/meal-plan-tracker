import pytest

import student
from conftest import FakeSession, make_student
from models import Student


def test_get_db_session(monkeypatch):
    session = FakeSession()
    created = {"tables": False}

    monkeypatch.setattr(
        student.Base.metadata, "create_all",
        lambda engine: created.update({"tables": True}),
    )
    monkeypatch.setattr(student, "SessionLocal", lambda: session)

    assert student.get_db_session() is session
    assert created["tables"] is True


def test_get_hardcoded_student_returns_existing():
    existing = make_student()
    session = FakeSession(student_obj=existing)

    result = student.get_hardcoded_student(session)

    assert result is existing
    assert session.added == []
    assert session.committed is False


def test_get_hardcoded_student_creates_new(monkeypatch):
    # Like SQLAlchemy's real constructor, this only accepts keyword arguments,
    # so positional construction (the current bug) fails here too.
    class FakeStudent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    monkeypatch.setattr(student, "Student", FakeStudent)
    session = FakeSession()

    result = student.get_hardcoded_student(session)

    assert result.id == 1
    assert result.name == "Test Student"
    assert result.swipes == 10
    assert result.village_flex == 25.00
    assert result.campus_flex == 15.00
    assert session.added == [result]
    assert session.committed is True
    assert session.refreshed is True


def test_get_hardcoded_student_creates_real_row_once(db):
    """Uses the real model + DB: catches constructor misuse."""
    session = db()
    try:
        first = student.get_hardcoded_student(session)
        second = student.get_hardcoded_student(session)

        assert first.id == second.id == 1
        assert (first.name, first.swipes, first.village_flex, first.campus_flex) == \
            ("Test Student", 10, 25.00, 15.00)
        assert session.query(Student).count() == 1
    finally:
        session.close()


def test_get_balances(monkeypatch):
    session = FakeSession(student_obj=make_student())
    monkeypatch.setattr(student, "get_db_session", lambda: session)

    assert student.get_balances() == {
        "student_id": 1,
        "name": "Test Student",
        "swipes": 10,
        "village_flex": 25.00,
        "campus_flex": 15.00,
    }
    assert session.closed is True


def test_get_balances_closes_session_on_error(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(student, "get_db_session", lambda: session)

    def raise_error(_):
        raise RuntimeError("Database error")

    monkeypatch.setattr(student, "get_hardcoded_student", raise_error)

    with pytest.raises(RuntimeError, match="Database error"):
        student.get_balances()

    assert session.closed is True
