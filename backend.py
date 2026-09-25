from database import SessionLocal
from models import Student, Transaction

def get_db_session():
    """Helper to create and return a database session."""
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
