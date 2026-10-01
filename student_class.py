from transaction_class import Transaction
from database import SessionLocal

class Student(object):
    def __init__(self, id, name):
        # class variable definitions
        self.id = id
        self.name = name
        self.transactions = []

    # class methods
    def startBalance(self,swipes,villageFlex,campusFlex):
        self.swipes = swipes
        self.villageFlex = villageFlex
        self.campusFlex = campusFlex

    def resetSwipes(self):
        pass

    #Version 1.0 hard-coded student
    #Retrieves ID=1 hardcoded student, if none then crea
    def get_hardcoded_student(session):
        student = session.get(Student, 1)
        if not student:
            student = Student(1, "Test Student", 10, 25.00, 15.00)

            session.add(student)
            session.commit()
            session.refresh(student)
        return student

    # TODO: Test this method
    def createTransaction(self, type, amount, location="", note=""):
        # Updates the balance, then creates a Transaction object to record the change
        # Validates type and amount before allowing input
        try:
            student = get_hardcoded_student(SessionLocal())

            if type not in ("swipe", "villageFlex","campusFlex"):  
                raise Exception("type must be 'swipe', 'villageFlex', or 'campusFlex'")
            if amount is None or amount <= 0:
                raise ValueError("Transaction amount must be greater than zero.")

            # Checks transaction type, valueCheck
            if(type == "swipe"):
                if student.swipes < amount:
                    raise ValueError("Insufficent swipes available.")
                self.swipes -= amount
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

            #Atomic change to database
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

    # TODO: Setters
    # getters
    def getID(self): return self.id
    def getName(self): return self.name
    def getSwipes(self): return self.swipes
    def getVillageFlex(self): return self.villageFlex
    def getCampusFlex(self): return self.campusFlex
    def getTransactionRecord(self): return self.transactions

