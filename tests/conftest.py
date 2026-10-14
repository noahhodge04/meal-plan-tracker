"""Shared fixtures for the Meal Plan Tracker tests.

IMPORTANT: the swap below must happen before `student`, `transaction` or `main`
are imported. conftest.py is loaded before any test module, so it does.

- main.py refuses to import without FLASK_SECRET_KEY, so we set one.
- database.engine / SessionLocal are replaced with a throwaway in-memory SQLite
  database, so the tests can never touch meal_tracker.db.

Test files never import from this file; everything is exposed as fixtures.
"""
import os
from types import SimpleNamespace

os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
import database

_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
database.engine = _test_engine
database.SessionLocal = sessionmaker(bind=_test_engine)




@pytest.fixture
def db():
    """Fresh empty tables for each test. Returns the SessionLocal factory."""
    database.Base.metadata.create_all(_test_engine)
    yield database.SessionLocal
    database.Base.metadata.drop_all(_test_engine)


@pytest.fixture
def session(db):
    s = db()
    yield s
    s.close()


@pytest.fixture
def seeded(db):
    """Three students.

    id=1: set up, 10 swipes, $25 village, $15 campus
    id=2: set up,  5 swipes, $10 village, $0 campus
    id=3: NOT set up (all zero)
    """
    from models import Student

    s = db()
    s.add(Student(id=1, name="Test Student", login_id="MP-00000001", password_hash="x",
                  swipes=10, starting_swipes=10, village_flex=25.00, campus_flex=15.00,
                  setup_completed=True))
    s.add(Student(id=2, name="Other Student", login_id="MP-00000002", password_hash="x",
                  swipes=5, starting_swipes=5, village_flex=10.00, campus_flex=0.00,
                  setup_completed=True))
    s.add(Student(id=3, name="Unconfigured", login_id="MP-00000003", password_hash="x"))
    s.commit()
    s.close()
    return db


# --------------------------------------------------------------------------
# Fakes for pure unit tests (no database)
# --------------------------------------------------------------------------
class FakeQuery:
    def __init__(self, rows, session):
        self.rows = list(rows)
        self.session = session

    def filter_by(self, **kwargs):
        self.session.filters.append(kwargs)
        self.rows = [
            r for r in self.rows
            if all(getattr(r, k, None) == v for k, v in kwargs.items())
        ]
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None

    def delete(self, **kwargs):
        self.session.delete_called = True
        gone = {id(r) for r in self.rows}
        self.session.transactions = [
            r for r in self.session.transactions if id(r) not in gone
        ]
        return len(gone)


class FakeSession:
    def __init__(self, student_obj=None, transactions=None, commit_error=None):
        self.student_obj = student_obj
        self.transactions = list(transactions or [])
        self.commit_error = commit_error

        self.added = []
        self.filters = []
        self.committed = False
        self.closed = False
        self.rolled_back = False
        self.refreshed = False
        self.delete_called = False

    def get(self, model, primary_key):
        # Behaves like a real lookup: wrong id -> None
        if self.student_obj is not None and self.student_obj.id == primary_key:
            return self.student_obj
        return None

    def add(self, obj):
        self.added.append(obj)

    def add_all(self, objects):
        self.added.extend(objects)

    def commit(self):
        if self.commit_error:
            raise self.commit_error
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def refresh(self, obj):
        self.refreshed = True

    def close(self):
        self.closed = True

    def query(self, model):
        return FakeQuery(self.transactions, self)


@pytest.fixture
def make_student():
    def _make(id=1, name="Test Student", login_id="MP-TEST0001", password_hash="hash",
              swipes=10, starting_swipes=10, village_flex=25.00, campus_flex=15.00,
              setup_completed=True):
        return SimpleNamespace(
            id=id, name=name, login_id=login_id, password_hash=password_hash,
            swipes=swipes, starting_swipes=starting_swipes,
            village_flex=village_flex, campus_flex=campus_flex,
            setup_completed=setup_completed,
        )
    return _make


@pytest.fixture
def make_session():
    def _make(student_obj=None, transactions=None, commit_error=None):
        return FakeSession(student_obj, transactions, commit_error)
    return _make


@pytest.fixture
def make_txn():
    def _make(id, student_id=1, type="swipe", amount=1.0, location="Hall", note="n"):
        return SimpleNamespace(id=id, student_id=student_id, type=type,
                               amount=amount, location=location, note=note)
    return _make
