"""Database model for user-owned accounts."""

from sqlalchemy import Column, ForeignKey, Integer, Numeric
from sqlalchemy.orm import relationship

from utils.db import Base


class Account(Base):
    """Database model for user-owned accounts."""

    __tablename__ = "accounts"

    account_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    balance = Column(Numeric(14, 2), nullable=False, default=0)

    user = relationship("User", back_populates="accounts")
    outgoing_transfers = relationship(
        "Transfer",
        back_populates="source_account",
        foreign_keys="Transfer.source_account_id",
        passive_deletes=True,
    )
    incoming_transfers = relationship(
        "Transfer",
        back_populates="destination_account",
        foreign_keys="Transfer.destination_account_id",
        passive_deletes=True,
    )
