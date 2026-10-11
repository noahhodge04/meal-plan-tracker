import pytest
from sqlalchemy.exc import IntegrityError

from models import Student, Transaction


@pytest.fixture
def session(db):
    s = db()
    yield s
    s.close()


def add_student(session, id, name="Test Student"):
    s = Student(id=id, name=name, swipes=10, village_flex=25.00, campus_flex=15.00)
    session.add(s)
    session.commit()
    return s


def test_student_model_attributes():
    s = Student(id=1, name="Test Student", swipes=10,
                village_flex=25.00, campus_flex=15.00)

    assert s.id == 1
    assert s.name == "Test Student"
    assert s.swipes == 10
    assert s.village_flex == 25.00
    assert s.campus_flex == 15.00


def test_student_defaults_applied_on_save(session):
    session.add(Student(id=1, name="Defaults"))
    session.commit()

    s = session.get(Student, 1)
    assert s.swipes == 0
    assert s.village_flex == 0.0
    assert s.campus_flex == 0.0


def test_student_requires_name(session):
    session.add(Student(id=1))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_student_persistence(session):
    add_student(session, 999, "Database Test Student")

    retrieved = session.get(Student, 999)

    assert retrieved is not None
    assert retrieved.name == "Database Test Student"
    assert retrieved.swipes == 10
    assert retrieved.village_flex == 25.00
    assert retrieved.campus_flex == 15.00


def test_transaction_persistence(session):
    add_student(session, 998)
    session.add(Transaction(student_id=998, type="swipe", amount=1,
                            location="Dining Hall", note="Lunch"))
    session.commit()

    t = session.query(Transaction).filter_by(student_id=998).first()

    assert t is not None
    assert t.type == "swipe"
    assert t.amount == 1
    assert t.location == "Dining Hall"
    assert t.note == "Lunch"


@pytest.mark.parametrize("missing", ["student_id", "type", "amount", "location", "note"])
def test_transaction_required_columns(session, missing):
    add_student(session, 1)
    fields = dict(student_id=1, type="swipe", amount=1,
                  location="Dining Hall", note="Lunch")
    fields.pop(missing)

    session.add(Transaction(**fields))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_student_transaction_relationship(session):
    add_student(session, 997, "Relationship Test Student")
    session.add(Transaction(student_id=997, type="swipe", amount=1,
                            location="Dining Hall", note="Lunch"))
    session.commit()

    t = session.query(Transaction).filter_by(student_id=997).first()

    # backref: Transaction -> Student
    assert t.student.id == 997
    assert t.student.name == "Relationship Test Student"

    # relationship: Student -> Transactions
    assert [x.id for x in t.student.transaction] == [t.id]


def test_multiple_transactions_for_student(session):
    add_student(session, 996)
    session.add_all([
        Transaction(student_id=996, type="swipe", amount=1,
                    location="Dining Hall", note="Lunch"),
        Transaction(student_id=996, type="village_flex", amount=5,
                    location="Village Market", note="Snack"),
        Transaction(student_id=996, type="campus_flex", amount=3,
                    location="Campus Store", note="Supplies"),
    ])
    session.commit()

    rows = (session.query(Transaction)
            .filter_by(student_id=996)
            .order_by(Transaction.id)
            .all())

    assert [r.type for r in rows] == ["swipe", "village_flex", "campus_flex"]


def test_transactions_are_separated_by_student(session):
    add_student(session, 995, "Student One")
    add_student(session, 994, "Student Two")
    session.add_all([
        Transaction(student_id=995, type="swipe", amount=1,
                    location="Dining Hall", note="Student One"),
        Transaction(student_id=994, type="campus_flex", amount=5,
                    location="Campus Store", note="Student Two"),
    ])
    session.commit()

    one = session.query(Transaction).filter_by(student_id=995).all()
    two = session.query(Transaction).filter_by(student_id=994).all()

    assert [t.note for t in one] == ["Student One"]
    assert [t.note for t in two] == ["Student Two"]
