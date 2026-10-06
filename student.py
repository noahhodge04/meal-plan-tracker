from database import Base, engine, SessionLocal
from models import Student, Transaction

def get_db_session():
    """Helper to create and return a database session."""
    Base.metadata.create_all(engine)
    return SessionLocal()

#Version 1.0 hard-coded student
#Retrieves ID=1 hardcoded student, if none then creates
def get_hardcoded_student(session):
    student = session.get(Student, 1)
    
    if not student:
        student = Student(
            id=1, 
            name="Test Student", 
            swipes=10, 
            village_flex=25.00, 
            campus_flex=15.00
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
        student = get_hardcoded_student(session)
        return {
            "student_id": student.id,
            "name": student.name,
            "swipes": student.swipes,
            "village_flex": student.village_flex,
            "campus_flex": student.campus_flex,
        }
    finally:
        session.close()

