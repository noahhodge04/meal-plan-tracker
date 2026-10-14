import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import configure_mappers

from models import Notification, Student, Transaction


def add_student(session, id, name="Test Student", login_id=None):
    s = Student(
        id=id,
        name=name,
        login_id=login_id or f"MP-{id}",
        password_hash="hash",
        swipes=10,
        starting_swipes=10,
        village_flex=25.00,
        campus_flex=15.00,
    )
    session.add(s)
    session.commit()
    return s


def add_txn(session, student_id, **overrides):
    fields = dict(student_id=student_id, type="swipe", amount=1,
                  location="Dining Hall", note="Lunch")
    fields.update(overrides)
    session.add(Transaction(**fields))
    session.commit()


def add_note(session, student_id, title="Title", message="Message"):
    session.add(Notification(student_id=student_id, title=title, message=message))
    session.commit()


def test_mappers_configure():
    """Fails if two relationships define the same attribute (e.g. a backref that
    collides with an explicit relationship on the other model)."""
    configure_mappers()


# --------------------------------------------------------------------------
# Student
# --------------------------------------------------------------------------
def test_student_model_attributes():
    s = Student(id=1, name="Test Student", login_id="MP-1", password_hash="h",
                swipes=10, starting_swipes=12, village_flex=25.00, campus_flex=15.00)

    assert (s.id, s.name, s.login_id, s.password_hash) == (1, "Test Student", "MP-1", "h")
    assert (s.swipes, s.starting_swipes, s.village_flex, s.campus_flex) == (10, 12, 25.00, 15.00)


def test_student_defaults_applied_on_save(session):
    session.add(Student(id=1, name="Defaults", login_id="MP-1", password_hash="h"))
    session.commit()

    s = session.get(Student, 1)
    assert s.swipes == 0
    assert s.starting_swipes == 0
    assert s.village_flex == 0.0
    assert s.campus_flex == 0.0
    assert s.setup_completed is False


@pytest.mark.parametrize("missing", ["name", "login_id", "password_hash"])
def test_student_required_columns(session, missing):
    fields = dict(id=1, name="N", login_id="MP-1", password_hash="h")
    fields.pop(missing)

    session.add(Student(**fields))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_student_login_id_must_be_unique(session):
    add_student(session, 1, login_id="MP-SAME")

    session.add(Student(id=2, name="Dup", login_id="MP-SAME", password_hash="h"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_student_persistence(session):
    add_student(session, 999, "Database Test Student")

    s = session.get(Student, 999)

    assert s is not None
    assert s.name == "Database Test Student"
    assert (s.swipes, s.starting_swipes, s.village_flex, s.campus_flex) == (10, 10, 25.00, 15.00)


# --------------------------------------------------------------------------
# Transaction
# --------------------------------------------------------------------------
def test_transaction_persistence(session):
    add_student(session, 998)
    add_txn(session, 998)

    t = session.query(Transaction).filter_by(student_id=998).first()

    assert t is not None
    assert (t.type, t.amount, t.location, t.note) == ("swipe", 1, "Dining Hall", "Lunch")


def test_transaction_location_and_note_default_to_empty_string(session):
    add_student(session, 1)
    session.add(Transaction(student_id=1, type="swipe", amount=1))
    session.commit()

    t = session.query(Transaction).first()
    assert t.location == ""
    assert t.note == ""


@pytest.mark.parametrize("missing", ["student_id", "type", "amount"])
def test_transaction_required_columns(session, missing):
    add_student(session, 1)
    fields = dict(student_id=1, type="swipe", amount=1)
    fields.pop(missing)

    session.add(Transaction(**fields))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_transaction_belongs_to_student(session):
    add_student(session, 997, "Relationship Test Student")
    add_txn(session, 997)

    t = session.query(Transaction).filter_by(student_id=997).first()

    assert t.student.id == 997
    assert t.student.name == "Relationship Test Student"


def test_multiple_transactions_for_student(session):
    add_student(session, 996)
    add_txn(session, 996, type="swipe", amount=1)
    add_txn(session, 996, type="village_flex", amount=5)
    add_txn(session, 996, type="campus_flex", amount=3)

    rows = (session.query(Transaction)
            .filter_by(student_id=996)
            .order_by(Transaction.id)
            .all())

    assert [r.type for r in rows] == ["swipe", "village_flex", "campus_flex"]


def test_transactions_are_separated_by_student(session):
    add_student(session, 995, "Student One")
    add_student(session, 994, "Student Two")
    add_txn(session, 995, note="Student One")
    add_txn(session, 994, note="Student Two", type="campus_flex", amount=5)

    one = session.query(Transaction).filter_by(student_id=995).all()
    two = session.query(Transaction).filter_by(student_id=994).all()

    assert [t.note for t in one] == ["Student One"]
    assert [t.note for t in two] == ["Student Two"]


# --------------------------------------------------------------------------
# Notification
# --------------------------------------------------------------------------
def test_notification_defaults(session):
    add_student(session, 1)
    add_note(session, 1, title="Hello", message="World")

    n = session.query(Notification).first()
    assert (n.student_id, n.title, n.message) == (1, "Hello", "World")
    assert n.is_read is False
    assert n.created_at is not None        # filled in by the database


@pytest.mark.parametrize("missing", ["student_id", "title", "message"])
def test_notification_required_columns(session, missing):
    add_student(session, 1)
    fields = dict(student_id=1, title="T", message="M")
    fields.pop(missing)

    session.add(Notification(**fields))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_notification_belongs_to_student(session):
    add_student(session, 1, "Owner")
    add_note(session, 1)

    assert session.query(Notification).first().student.name == "Owner"


# --------------------------------------------------------------------------
# Cascades
# --------------------------------------------------------------------------
def test_deleting_student_deletes_their_transactions_and_notifications(session):
    add_student(session, 1)
    add_student(session, 2)
    add_txn(session, 1)
    add_txn(session, 2)
    add_note(session, 1)
    add_note(session, 2)

    session.delete(session.get(Student, 1))
    session.commit()

    assert [t.student_id for t in session.query(Transaction).all()] == [2]
    assert [n.student_id for n in session.query(Notification).all()] == [2]
