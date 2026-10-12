
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from werkzeug.security import check_password_hash, generate_password_hash

import student as student_module
from database import Base
from models import Student


@pytest.fixture
def test_db(monkeypatch):
    """Give each test an isolated database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    TestSession = sessionmaker(bind=engine)

    monkeypatch.setattr(
        student_module,
        "get_db_session",
        TestSession,
    )

    yield TestSession

    engine.dispose()

@pytest.mark.parametrize(
    "name,password",
    [
        ("", "safe-password-123"),
        ("   ", "safe-password-123"),
        ("Valid Name", ""),
        ("Valid Name", "short"),
    ],
)
def test_registration_rejects_invalid_input(name, password):
    with pytest.raises(ValueError):
        student_module.create_student(name, password)
        

def test_create_student_success(test_db):
    result = student_module.create_student(
        "New Student",
        "safe-password-123",
    )

    with test_db() as session:
        saved = session.get(Student, result["student_id"])

        assert saved is not None
        assert saved.name == "New Student"
        assert saved.login_id == result["login_id"]
        assert saved.login_id.startswith("MP-")
        assert saved.swipes == 0
        assert saved.village_flex == 0.0
        assert saved.campus_flex == 0.0


def test_create_student_hashes_password(test_db):
    password = "safe-password-123"

    result = student_module.create_student(
        "Password Test",
        password,
    )

    with test_db() as session:
        saved = session.get(Student, result["student_id"])

        assert saved.password_hash != password
        assert check_password_hash(
            saved.password_hash,
            password,
        )
        assert not check_password_hash(
            saved.password_hash,
            "wrong-password",
        )


@pytest.mark.parametrize("name", ["", "   ", None])
def test_create_student_rejects_invalid_name(test_db, name):
    with pytest.raises(ValueError, match="name"):
        student_module.create_student(
            name,
            "safe-password-123",
        )


@pytest.mark.parametrize(
    "password",
    ["", "short", None],
)
def test_create_student_rejects_short_password(
    test_db,
    password,
):
    with pytest.raises(ValueError, match="Password"):
        student_module.create_student(
            "Password Test",
            password,
        )

def test_registration_hashes_password(test_db):
    password = "safe-password-123"

    new_student = student_module.create_student(
        "Password Test Student",
        password,
    )

    with test_db() as session:
        saved_student = session.get(
            Student,
            new_student["student_id"],
        )

        assert saved_student is not None
        assert saved_student.password_hash != password
        assert check_password_hash(
            saved_student.password_hash,
            password,
        )
        assert not check_password_hash(
            saved_student.password_hash,
            "wrong-password",
        )


def test_registration_preserves_existing_student(test_db):
    with test_db() as session:
        existing = Student(
            id=1,
            name="Existing Student",
            login_id="MP-EXIST01",
            password_hash=generate_password_hash("existing-test-password"),
            swipes=10,
            village_flex=25.0,
            campus_flex=15.0,
        )
        session.add(existing)
        session.commit()

    new_student = student_module.create_student(
        "Second Student",
        "safe-password-123",
    )

    with test_db() as session:
        existing = session.get(Student, 1)

        assert existing.name == "Existing Student"
        assert existing.swipes == 10
        assert existing.village_flex == 25.0
        assert existing.campus_flex == 15.0

        assert new_student["student_id"] != existing.id