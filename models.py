from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import relationship

from database import Base


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        Index("uq_students_login_id", "login_id", unique=True),
        Index("uq_students_username", "name", unique=True),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    login_id = Column(String(20), nullable=False)
    password_hash = Column(String(255), nullable=False)

    swipes = Column(Integer, nullable=False, default=0)
    starting_swipes = Column(Integer, nullable=False, default=0)
    village_flex = Column(Float, nullable=False, default=0.0)
    campus_flex = Column(Float, nullable=False, default=0.0)
    setup_completed = Column(Boolean, nullable=False, default=False)
    swipe_alert_threshold = Column(Integer, nullable=True)
    village_flex_alert_threshold = Column(Float, nullable=True)
    campus_flex_alert_threshold = Column(Float, nullable=True)

    transactions = relationship(
        "Transaction",
        back_populates="student",
        cascade="all, delete-orphan"
    )
    notifications = relationship(
        "Notification",
        back_populates="student",
        cascade="all, delete-orphan"
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    student_id = Column(
        Integer,
        ForeignKey("students.id"),
        nullable=False,
        index=True
    )
    type = Column(String(20), nullable=False)
    amount = Column(Float, nullable=False)
    location = Column(String(100), nullable=False, default="")
    note = Column(String(255), nullable=False, default="")

    student = relationship(
        "Student",
        back_populates="transactions"
    )


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    title = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    student = relationship(
        "Student",
        back_populates="notifications"
    )
