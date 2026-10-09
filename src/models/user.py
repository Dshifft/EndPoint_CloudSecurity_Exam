"""Database model for registered banking users."""

from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship

from utils.db import Base


class User(Base):
    """Database model for registered banking users."""

    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(Text, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    accounts = relationship(
        "Account",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    token_sessions = relationship(
        "TokenSession",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
