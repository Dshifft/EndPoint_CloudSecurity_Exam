"""Request and response schemas for account and transfer endpoints."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class AccountBalanceUpdateData(BaseModel):
    """Amount to deposit into or withdraw from an account."""

    amount: Decimal = Field(max_digits=14, decimal_places=2)

    @field_validator("amount")
    @classmethod
    def validate_non_zero_amount(cls, amount: Decimal) -> Decimal:
        """Reject balance updates that would not change the account."""
        if amount == Decimal("0.00"):
            raise ValueError("Amount must be positive or negative.")
        return amount


class AccountResponse(BaseModel):
    """Account data returned to its owner."""

    account_id: int
    user_id: int
    balance: Decimal


class TransferCreateData(BaseModel):
    """Data required to move funds between two accounts."""

    source_account_id: int
    destination_account_id: int
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    note: str


class TransferResponse(BaseModel):
    """Transfer data with its note decrypted for the response."""

    transfer_id: int
    source_account_id: int
    destination_account_id: int
    amount: Decimal
    note: str
    created_at: datetime
