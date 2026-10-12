from database import Base, engine, SessionLocal
from models import Student, Transaction

import secrets

from werkzeug.security import generate_password_hash
from sqlalchemy.exc import IntegrityError


def get_db_session():
    """Helper to create and return a database session."""
    Base.metadata.create_all(engine)
    return SessionLocal()

def get_hardcoded_student(session):
    student = session.get(Student, 1)
    
    if not student:
        student = Student(
            id=1, 
            name="Test Student", 
            login_id=f"MP-{secrets.token_hex(4).upper()}",
             password_hash=generate_password_hash(
                secrets.token_urlsafe(32)
                ),

            swipes=10, 
            village_flex=25.00, 
            campus_flex=15.00
        )

        session.add(student)
        session.commit()
        session.refresh(student)
    return student


def get_student_by_id(session, student_id):
    """Retrieve a student by database ID or raise an error."""

    student = session.get(Student, student_id)

    if student is None:
        raise LookupError(f"Student with ID {student_id} was not found.")

    return student


def create_student(name, password):
    """Create a student account with a generated login ID and zero balances."""

    if not isinstance(name, str) or not name.strip():
        raise ValueError("Student name is required.")

    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")

    name = name.strip()
    session = get_db_session()

    try:
        # Generate a login ID that is not already in use.
        while True:
            login_id = f"MP-{secrets.token_hex(4).upper()}"

            existing_student = (
                session.query(Student)
                .filter_by(login_id=login_id)
                .first()
            )

            if existing_student is None:
                break

        student = Student(
            name=name,
            login_id=login_id,
            password_hash=generate_password_hash(password),
            swipes=0,
            village_flex=0.0,
            campus_flex=0.0,
        )

        session.add(student)
        session.commit()
        session.refresh(student)

        return {
            "student_id": student.id,
            "login_id": student.login_id,
            "name": student.name,
            "swipes": student.swipes,
            "village_flex": student.village_flex,
            "campus_flex": student.campus_flex,
        }

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


def get_balances(student_id):
    """Return balances for a specific student."""

    session = get_db_session()

    try:
        student = get_student_by_id(session, student_id)

        return {
            "student_id": student.id,
            "login_id": student.login_id,
            "name": student.name,
            "swipes": student.swipes,
            "village_flex": student.village_flex,
            "campus_flex": student.campus_flex,
        }
    finally:
        session.close()