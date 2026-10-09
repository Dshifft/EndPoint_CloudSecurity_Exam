"""Database model for account-to-account transfers."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.orm import relationship

from utils.db import Base


class Transfer(Base):
    """Database model for an account-to-account transfer."""

    __tablename__ = "transfers"

    transfer_id = Column(Integer, primary_key=True, index=True)
    source_account_id = Column(
        Integer,
        ForeignKey("accounts.account_id", ondelete="CASCADE"),
        nullable=False,
    )
    destination_account_id = Column(
        Integer,
        ForeignKey("accounts.account_id", ondelete="CASCADE"),
        nullable=False,
    )
    amount = Column(Numeric(14, 2), nullable=False)
    encrypted_note = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    source_account = relationship(
        "Account",
        back_populates="outgoing_transfers",
        foreign_keys=[source_account_id],
    )
    destination_account = relationship(
        "Account",
        back_populates="incoming_transfers",
        foreign_keys=[destination_account_id],
    )
