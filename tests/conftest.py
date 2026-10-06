"""Shared test helpers for the Meal Plan Tracker suite."""
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401  (registers tables on Base.metadata)
import student
import transaction
from database import Base


# --------------------------------------------------------------------------
# Fakes for pure unit tests (no database)
# --------------------------------------------------------------------------
class FakeQuery:
    def __init__(self, rows, session=None):
        self.rows = list(rows)
        self.session = session

    def filter_by(self, **kwargs):
        self.rows = [
            r for r in self.rows
            if all(getattr(r, k) == v for k, v in kwargs.items())
        ]
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None

    def delete(self):
        if self.session is not None:
            self.session.delete_called = True


class FakeSession:
    def __init__(self, student_obj=None, transactions=None, commit_error=None):
        self.student_obj = student_obj
        self.transactions = transactions or []
        self.commit_error = commit_error

        self.added = []
        self.committed = False
        self.closed = False
        self.rolled_back = False
        self.refreshed = False
        self.delete_called = False

    def get(self, model, primary_key):
        return self.student_obj

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
        return FakeQuery(self.transactions, session=self)


def make_student(id=1, name="Test Student", swipes=10,
                 village_flex=25.00, campus_flex=15.00):
    return SimpleNamespace(
        id=id, name=name, swipes=swipes,
        village_flex=village_flex, campus_flex=campus_flex,
    )


# --------------------------------------------------------------------------
# Real in-memory database (never touches meal_tracker.db)
# --------------------------------------------------------------------------
@pytest.fixture
def db(monkeypatch):
    """Returns a sessionmaker bound to a throwaway in-memory SQLite DB.

    The 'student' and 'transaction' modules are redirected to it, so their
    get_db_session() helpers use the test DB too.
    """
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(bind=test_engine)

    for module in (student, transaction):
        monkeypatch.setattr(module, "engine", test_engine)
        monkeypatch.setattr(module, "SessionLocal", TestSession)

    Base.metadata.create_all(test_engine)
    yield TestSession
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()
