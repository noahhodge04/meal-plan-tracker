from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship

from database import Base

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)

    swipes = Column(Integer, default=0)
    village_flex = Column(Float, default=0.0)
    campus_flex = Column(Float, default=0.0)

    transaction = relationship(
        "Transaction",
        backref="student",
        lazy=True
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)

    student_id = Column(
        Integer,
        ForeignKey("students.id"),
        nullable=False
    )

    type = Column(String(20), nullable=False)
    amount = Column(Float, nullable=False)
    location = Column(String(100), nullable=False)
    note =  Column(String(255), nullable=False)