from student_class import Student


def test_student_creation():
    student = Student(1, "Test Student")

    assert student.getID() == 1
    assert student.getName() == "Test Student"


def test_start_balance():
    student = Student(1, "Test Student")

    student.startBalance(10, 25.00, 15.00)

    assert student.getSwipes() == 10
    assert student.getVillageFlex() == 25.00
    assert student.getCampusFlex() == 15.00


def test_create_swipe_transaction():
    student = Student(1, "Test Student")
    student.startBalance(10, 25.00, 15.00)

    student.createTransaction("swipe", 1, "Dining Hall", "Lunch")

    assert student.getSwipes() == 9


def test_create_village_flex_transaction():
    student = Student(1, "Test Student")
    student.startBalance(10, 25.00, 15.00)

    student.createTransaction("villageFlex", 5.00, "Village Market", "Snack")

    assert student.getVillageFlex() == 20.00


def test_create_campus_flex_transaction():
    student = Student(1, "Test Student")
    student.startBalance(10, 25.00, 15.00)
    
    student.createTransaction("campusFlex", 5.00, "Campus Store", "Supplies")
    
    assert student.getCampusFlex() == 10.00


def test_village_flex_rollover():
    student = Student(1, "Test Student")
    student.startBalance(10, 5.00, 15.00)
    
    student.createTransaction("villageFlex", 8.00, "Village Market", "Food")

    assert student.getVillageFlex() == 0.00
    assert student.getCampusFlex() == 12.00


def test_transaction_history():
    student = Student(1, "Test Student")
    student.startBalance(10, 25.00, 15.00)

    student.createTransaction("swipe", 1, "Dining Hall", "Lunch")

    transactions = student.getTransactionRecord()

    assert len(transactions) == 1


def test_transaction_details():
    student = Student(1, "Test Student")
    student.startBalance(10, 25.00, 15.00)

    student.createTransaction("swipe", 1, "Dining Hall", "Lunch")

    transaction = student.getTransactionRecord()[0]

    assert transaction.type == "swipe"
    assert transaction.amount == 1
    assert transaction.location == "Dining Hall"
    assert transaction.note == "Lunch"


def test_invalid_transaction_type():
    student = Student(1, "Test Student")
    student.startBalance(10, 25.00, 15.00)

    try:
        student.createTransaction("invalidType", 5.00)
        assert False
    except Exception:
        assert True


def test_negative_transaction_amount():
    student = Student(1, "Test Student")
    student.startBalance(10, 25.00, 15.00)

    try:
        student.createTransaction("swipe", -1, "Dining Hall", "Lunch")
        assert False
    except Exception:
        assert True


def test_zero_transaction_amount():
    student = Student(1, "Test Student")
    student.startBalance(10, 25.00, 15.00)

    try:
        student.createTransaction("swipe", 0, "Dining Hall", "Lunch")
        assert False
    except Exception:
        assert True