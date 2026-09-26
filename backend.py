from database import engine, SessionLocal
from models import Base, Student, Transaction

def get_db_session():
    """Helper to create and return a database session."""
    Base.metadata.create_all(engine)
    return SessionLocal()


def get_or_create_hardcoded_student(session):
    """
    Retrieves the primary hard-coded student (ID = 1).
    If the student does not exist yet, creates them with starting balances.
    """
    student = session.get(Student, 1)
    if not student:
        student = Student(
            id=1,
            name="test Student",
            swipes=10,
            village_flex=25.00,
            campus_flex=15.00,
        )
        session.add(student)
        session.commit()
        session.refresh(student)
    return student

def get_balances():
    """
    Retrieves the current student's balances in a plain dictionary format.
    """
    session = get_db_session()
    try:
        student = get_or_create_hardcoded_student(session)
        return {
            "student_id": student.id,
            "name": student.name,
            "swipes": student.swipes,
            "village_flex": student.village_flex,
            "campus_flex": student.campus_flex,
        }
    finally:
        session.close()
def create_transaction(transaction_type, amount, location="", note=""):
    """
    Validates input, updates student balances (including Village Flex rollover),
    and records the transaction in the database.
    """
    #1. Validation
    valid_types = ("swipe", "villageFlex", "campusFlex")
    if transaction_type not in valid_types:
        raise ValueError(f"Invalid transaction type. Must be one of {valid_types}")

    if amount is None or amount <=0:
        raise ValueError("Transaction amount must be greater than zero.")

    session = get_db_session()
    try:
        student = get_or_create_hardcoded_student(session)

        #2. Check sufficient funds & compute balance changes
        if transaction_type == "swipe":
            if student.swipes < amount:
                raise ValueError("Insufficient swipes available.")
            student.swipes -= int(amount)

        elif transaction_type == "campusFlex":
            if student.campus_flex < amount:
                raise ValueError("Insufficient Campus Flex balance")
            student.campus_flex -= amount

        elif transaction_type == "villageFlex":
            total_flex = student.village_flex + student.campus_flex
            if total_flex < amount:
                raise ValueError("Insufficient total Flex balance.")

            if student.village_flex >= amount:
                student.village_flex -=amount
            else:
                #Rollover logic: deplete Village Flex, remainder comes from Campus Flex
                remainder = amount - student.village_flex
                student.village_flex = 0.0
                student.campus_flex -= remainder
            #3 Record transaction entry
        txn = Transaction(
            student_id=student.id,
            type=transaction_type,
            amount=float(amount),
            location=location,
            note=note
        )
        session.add(txn)

        #4. Save atomic changes to database
        session.commit()

        return {
            "status": "success",
            "swipes": student.swipes,
            "village_flex": student.village_flex,
            "campus_flex": student.campus_flex
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def get_transactions():
    """Retrieves all transaction history for the student, newest first."""
    session= get_db_session()
    try:
        student = get_or_create_hardcoded_student(session)
        txns = session.query(Transaction).filter_by(student_id=student.id).order_by(Transaction.id.desc()).all()

        return [
            {
                "id": t.id,
                "type": t.type,
                "amount": t.amount,
                "location": t.location,
                "note": t.note,
            }
            for t in txns
        ]
    finally:
        session.close()

def clear_transactions():
    #Clears the transaction history
    session = get_db_session()
    try:
        #Delete all transaction records of the student
        session.query(Transaction).delete()

        session.commit()
    finally:
        session.close()
