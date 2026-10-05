from database import Base, engine, SessionLocal
from models import Student, Transaction

from student import get_hardcoded_student


#Create/return a database session
def get_db_session():
    Base.metadata.create_all(engine)
    return SessionLocal()

#Validate input, update student balances, and record the transaction
def create_transaction(self, type, amount, location="", note=""):
    # Updates the balance, then creates a Transaction object to record the change
    # Validates type and amount before allowing input
    student = get_hardcoded_student(SessionLocal())

    valid_types = ("swipe", "villageFlex","campusFlex")
    if type not in valid_types:  
        raise ValueError(f"Invalid transaction type. Must be one of {valid_types}")
            
    if amount is None or amount <= 0:
        raise ValueError("Transaction amount must be greater than zero.")

    session = get_db_session()

    try:
        student = get_hardcoded_student(session)
        # Checks transaction type, valueCheck
        if(type == "swipe"):
            if student.swipes < amount:
                raise ValueError("Insufficent swipes available.")
            
            self.swipes -= int(amount)

        elif(type == "campusFlex"):
            if student.campusFlex < amount:
                raise ValueError("Insufficient Campus Flex balnace")
            
            student.campus_flex -= amount

        elif(type == "villageFlex"):
            total_flex = student.village_flex + student.campus_flex
            if total_flex < amount:
                raise ValueError("Insufficient total Flex balance")

            if student.village_flex >= amount:
                student.village_flex -= amount
            else:
                #Deplete Village, pull from Campus
                remainder = amount -student.villageFlex
                student.village_flex = 0.0
                student.campusFlex -= remainder

        # Transaction record
        txn = Transaction(
            student_id=student.id,
            type=type,
            amount=float(amount),
            location=location,
            note=note
        )
        SessionLocal.add(txn)
        SessionLocal.commit()

        return {
            "status": "success",
            "swipes": student.swipes,
            "village_flex": student.village_flex,
            "campus_flex": student.campus_flex
        }
    except Exception:
        SessionLocal.rollback()
        raise
    finally:
        SessionLocal.close()

#Retrieve all transaction history for the student, newest first.
def get_transactions():

    session = get_db_session()

    try:
        student = get_hardcoded_student
        txns = (session.query(Transaction).filter_by(student_id=student.id).order_by(Transaction.id.desc()).all())

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


#Clear the transaction history.
def clear_transactions():

    session = get_db_session()

    try:
        session.query(Transaction).delete()
        session.commit()

    finally:
        session.close()
