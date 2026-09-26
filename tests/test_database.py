from database import Base, engine, SessionLocal
from models import Student, Transaction


def test_student_model():
    student = Student(id=1, name="Test Student", swipes=10, village_flex=25.00, campus_flex=15.00)

    assert student.id == 1
    assert student.name == "Test Student"
    assert student.swipes == 10
    assert student.village_flex == 25.00
    assert student.campus_flex == 15.00


def test_student_database_persistence():
    Base.metadata.create_all(engine)

    session = SessionLocal()

    existing_student = session.get(Student, 999)

    if existing_student is not None:
        session.delete(existing_student)
        session.commit()

    student = Student(
        id=999, name="Database Test Student", swipes=10, village_flex=25.00, campus_flex=15.00
    )

    session.add(student)
    session.commit()

    retrieved_student = session.get(Student, 999)

    assert retrieved_student is not None
    assert retrieved_student.name == "Database Test Student"
    assert retrieved_student.swipes == 10
    assert retrieved_student.village_flex == 25.00
    assert retrieved_student.campus_flex == 15.00

    session.close()


    
def test_transaction_database_persistence():
    Base.metadata.create_all(engine)

    session = SessionLocal()

    existing_transactions = session.query(Transaction).filter_by(student_id=998).all()
    for existing_transaction in existing_transactions:
        session.delete(existing_transaction)

    existing_student = session.get(Student, 998)

    if existing_student is not None:
        session.delete(existing_student)
        session.commit()

    student = Student(
        id=998,
        name="Transaction Test Student",
        swipes=10,
        village_flex=25.00,
        campus_flex=15.00
    )

    session.add(student)
    session.commit()

    transaction = Transaction(
        student_id=998,
        type="swipe",
        amount=1,
        location="Dining Hall",
        note="Lunch"
    )

    session.add(transaction)
    session.commit()

    retrieved_transaction = session.query(Transaction).filter_by(
        student_id=998
    ).first()

    assert retrieved_transaction is not None
    assert retrieved_transaction.type == "swipe"
    assert retrieved_transaction.amount == 1
    assert retrieved_transaction.location == "Dining Hall"
    assert retrieved_transaction.note == "Lunch"
    assert retrieved_transaction.student_id == 998

    session.close()


def test_student_transaction_relationship():
    Base.metadata.create_all(engine)

    session = SessionLocal()

    existing_transactions = session.query(Transaction).filter_by(student_id=997).all()
    for existing_transaction in existing_transactions:
        session.delete(existing_transaction)

    existing_student = session.get(Student, 997)

    if existing_student is not None:
        session.delete(existing_student)
        session.commit()

    student = Student(
        id=997,
        name="Relationship Test Student",
        swipes=10,
        village_flex=25.00,
        campus_flex=15.00
    )

    session.add(student)
    session.commit()

    transaction = Transaction(
        student_id=997,
        type="swipe",
        amount=1,
        location="Dining Hall",
        note="Lunch"
    )

    session.add(transaction)
    session.commit()

    retrieved_transaction = session.query(Transaction).filter_by(
        student_id=997
    ).first()

    assert retrieved_transaction is not None
    assert retrieved_transaction.student_id == 997
    assert retrieved_transaction.student.id == 997
    assert retrieved_transaction.student.name == "Relationship Test Student"

    session.close()

