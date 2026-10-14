import math

from database import SessionLocal
from models import Notification, Student, Transaction
from student import get_student_by_id


def get_db_session():
    return SessionLocal()


def create_transaction(student_id, type, amount, location="", note=""):
    """Validate a transaction, update the student's balance, and record it."""

    valid_types = ("swipe", "village_flex", "campus_flex")
    if type not in valid_types:
        raise ValueError(f"Invalid transaction type. Must be one of {valid_types}.")

    if isinstance(amount, bool):
        raise ValueError("Transaction amount must be greater than zero.")

    try:
        amount = float(amount)

    except (TypeError, ValueError):
        raise ValueError("Transaction amount must be a number greater than zero.")

    if not math.isfinite(amount) or amount <= 0:
        raise ValueError("Transaction amount must be a finite number greater than zero.")

    if type == "swipe" and not amount.is_integer():
        raise ValueError("Swipe transaction amounts must be whole numbers.")

    if not isinstance(location, str) or len(location) > 100:
        raise ValueError("Location must be 100 characters or fewer.")

    if not isinstance(note, str) or len(note) > 255:
        raise ValueError("Note must be 255 characters or fewer.")

    session = get_db_session()

    try:
        student = get_student_by_id(session, student_id)

        if not student.setup_completed:
            raise ValueError("Complete initial balance setup before recording transactions.")

        previous_balances = {
            "swipe_alert_threshold": student.swipes,
            "village_flex_alert_threshold": student.village_flex,
            "campus_flex_alert_threshold": student.campus_flex,
        }

        if type == "swipe":
            if student.swipes < amount:
                raise ValueError("Insufficient swipes available.")
            student.swipes -= int(amount)
        elif type == "campus_flex":
            if student.campus_flex < amount:
                raise ValueError("Insufficient Campus Flex balance.")
            student.campus_flex = round(student.campus_flex - amount, 2)
        else:
            if student.village_flex + student.campus_flex < amount:

                raise ValueError("Insufficient total Flex balance.")

            from_village = min(student.village_flex, amount)

            student.village_flex = round(student.village_flex - from_village, 2)
            student.campus_flex = round(student.campus_flex - (amount - from_village), 2)

        session.add(Transaction(
            student_id=student.id,
            type=type,
            amount=amount,
            location=location.strip(),
            note=note.strip(),
        ))
        session.add(Notification(
            student_id=student.id,
            title="Meal-plan transaction recorded",
            message=f"A {type.replace('_', ' ')} transaction for {amount:g} was recorded.",
        ))
        low_balance_fields = (
            ("swipe_alert_threshold", "Swipes", student.swipe_alert_threshold, student.swipes),
            (
                "village_flex_alert_threshold",
                "Village Flex",
                student.village_flex_alert_threshold,
                student.village_flex,
            ),
            (
                "campus_flex_alert_threshold",
                "Campus Flex",
                student.campus_flex_alert_threshold,
                student.campus_flex,
            ),
        )
        for threshold_field, label, threshold, current_balance in low_balance_fields:
            if (
                threshold is not None
                and previous_balances[threshold_field] > threshold
                and current_balance <= threshold
            ):
                formatted_balance = (
                    f"{current_balance} swipe{'s' if current_balance != 1 else ''}"
                    if threshold_field == "swipe_alert_threshold"
                    else f"${current_balance:.2f}"
                )
                session.add(Notification(
                    student_id=student.id,
                    title=f"Low {label} balance",
                    message=f"Your {label} balance is now {formatted_balance}.",
                ))
        session.commit()

        return {
            "status": "success",
            "swipes": student.swipes,
            "village_flex": student.village_flex,
            "campus_flex": student.campus_flex,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_transactions(student_id):
    """Retrieve a student's transaction history, newest first."""

    session = get_db_session()
    try:
        student = get_student_by_id(session, student_id)
        txns = (
            session.query(Transaction)
            .filter_by(student_id=student.id)
            .order_by(Transaction.id.desc())
            .all()
        )
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


def clear_transactions(student_id):
    """Clear transaction history for one student only; does not change balances."""

    session = get_db_session()

    try:
        get_student_by_id(session, student_id)
        session.query(Transaction).filter_by(
            student_id=student_id).delete(synchronize_session=False)
        session.commit()
    except Exception:
        session.rollback()
        raise

    finally:
        session.close()