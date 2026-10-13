from database import Base, engine, SessionLocal
from models import Notification, Student, Transaction

import secrets

from werkzeug.security import generate_password_hash
from sqlalchemy.exc import IntegrityError


def get_db_session():
    """Create a database session. Tables are initialized by main.py at startup."""
    Base.metadata.create_all(engine)
    return SessionLocal()


def get_student_by_id(session, student_id):
    """Retrieve a student by database ID or raise an error."""

    student = session.get(Student, student_id)

    if student is None:
        raise LookupError(f"Student with ID {student_id} was not found.")

    return student


def create_student(name, password):
    """Create a student account with a generated login ID and unconfigured balances."""

    if not isinstance(name, str) or not name.strip():
        raise ValueError("Student name is required.")

    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")

    session = get_db_session()

    try:
        name = name.strip()
        for _ in range(10):
            login_id = f"MP-{secrets.token_hex(4).upper()}"
            if session.query(Student.id).filter_by(login_id=login_id).first() is None:
                break
        else:
            raise RuntimeError("Could not generate a unique login ID. Please try again.")

        student = Student(
            name=name,
            login_id=login_id,
            password_hash=generate_password_hash(password),
            swipes=0,
            starting_swipes=0,
            village_flex=0.0,
            campus_flex=0.0,
            setup_completed=False,
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
            "setup_completed": student.setup_completed,
        }

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


def get_balances(student_id):
    """Return current balances and initial-setup status for one student."""

    session = get_db_session()

    try:
        student = get_student_by_id(session, student_id)

        return {
            "student_id": student.id,
            "login_id": student.login_id,
            "name": student.name,
            "swipes": student.swipes,
            "starting_swipes": student.starting_swipes,
            "village_flex": student.village_flex,
            "campus_flex": student.campus_flex,
            "setup_completed": student.setup_completed,
        }
    finally:
        session.close()


def set_starting_balances(student_id, swipes, village_flex, campus_flex):
    """Set starting balances once. These values cannot be changed after setup."""

    if isinstance(swipes, bool) or not isinstance(swipes, int) or swipes < 0:
        raise ValueError("Starting swipes must be a nonnegative whole number.")

    village_flex = _validate_money_balance(village_flex, "Village Flex")
    campus_flex = _validate_money_balance(campus_flex, "Campus Flex")

    session = get_db_session()

    try:
        student = get_student_by_id(session, student_id)
        if student.setup_completed:
            raise ValueError("Starting balances have already been configured and cannot be changed.")

        student.swipes = swipes
        student.starting_swipes = swipes
        student.village_flex = village_flex
        student.campus_flex = campus_flex
        student.setup_completed = True
        session.add(Notification(
            student_id=student.id,
            title="Starting balances saved",
            message="Your initial meal-plan balances have been saved.",
        ))

        session.commit()

        return {
            "student_id": student.id,
            "swipes": student.swipes,
            "starting_swipes": student.starting_swipes,
            "village_flex": student.village_flex,
            "campus_flex": student.campus_flex,
            "setup_completed": student.setup_completed,
        }

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _validate_money_balance(value, label):

    if isinstance(value, bool):
        raise ValueError(f"{label} balance must be a nonnegative number.")

    try:
        amount = float(value)

    except (TypeError, ValueError):
        raise ValueError(f"{label} balance must be a nonnegative number.")

    if amount < 0 or amount != amount or amount == float("inf") or amount == float("-inf"):
        raise ValueError(f"{label} balance must be a finite, nonnegative number.")

    return round(amount, 2)


def reset_swipes_to_starting_balance(student_id):
    """Restore current swipes to the student's saved starting swipe balance."""

    session = get_db_session()

    try:
        student = get_student_by_id(session, student_id)
        if not student.setup_completed:
            raise ValueError("Complete initial balance setup before resetting swipes.")

        previous_swipes = student.swipes
        student.swipes = student.starting_swipes

        session.add(Transaction(
            student_id=student.id,
            type="swipe_reset",
            amount=float(student.starting_swipes),
            location="",
            note=f"Manual reset from {previous_swipes} to {student.starting_swipes} swipes.",
        ))

        session.add(Notification(
            student_id=student.id,
            title="Swipes reset",
            message=f"Your swipe balance was reset to {student.starting_swipes} swipes.",
        ))

        session.commit()
        return {
            "student_id": student.id,
            "previous_swipes": previous_swipes,
            "swipes": student.swipes,
            "starting_swipes": student.starting_swipes,
        }

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()
