"""Account and transfer endpoints for authenticated banking users."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.account.accountSchema import (
    AccountBalanceUpdateData,
    AccountResponse,
    TransferCreateData,
    TransferResponse,
)
from src.models.account import Account
from src.models.transfer import Transfer
from utils.constants import Endpoints
from utils.data_types import UserJWTPayload
from utils.db import get_db
from utils.security import decrypt_transfer_note, encrypt_transfer_note, validate_user_jwt_token


account_router = APIRouter(tags=["accounts", "transfers"])


def get_account_response(account: Account) -> AccountResponse:
    """Build an account response for its authenticated owner."""
    return AccountResponse(
        account_id=account.account_id,
        user_id=account.user_id,
        balance=account.balance,
    )


def get_owned_account(
    account_id: int,
    payload: UserJWTPayload,
    db: Session,
    lock: bool = False,
) -> Account:
    """Return an account only when it belongs to the token holder."""
    account_query = db.query(Account).filter(Account.account_id == account_id)
    if lock:
        account_query = account_query.with_for_update()
    account = account_query.first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    if account.user_id != payload.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this account is forbidden.")
    return account


@account_router.post(
    Endpoints.ACCOUNTS,
    status_code=status.HTTP_201_CREATED,
    response_model=AccountResponse,
    summary="Create an account",
    description="Creates a new account for the bearer-token owner with a balance of 0.00.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "The bearer token is missing, invalid, or revoked."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "The account could not be created."},
    },
)
def create_account(
    payload: UserJWTPayload = Depends(validate_user_jwt_token),
    db: Session = Depends(get_db),
) -> AccountResponse:
    """Create a zero-balance account for the token holder.

    Input: a valid bearer token. Output: the created account with its initial balance.
    """
    account = Account(user_id=payload.user_id, balance=Decimal("0.00"))
    db.add(account)
    try:
        db.commit()
        db.refresh(account)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")
    return get_account_response(account)


@account_router.get(
    Endpoints.ACCOUNTS,
    response_model=list[AccountResponse],
    summary="List owned accounts",
    description="Returns every account owned by the bearer-token owner.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "The bearer token is missing, invalid, or revoked."},
    },
)
def get_accounts(
    payload: UserJWTPayload = Depends(validate_user_jwt_token),
    db: Session = Depends(get_db),
) -> list[AccountResponse]:
    """Return every account owned by the token holder.

    Input: a valid bearer token. Output: a list of the user's accounts and balances.
    """
    accounts = db.query(Account).filter(Account.user_id == payload.user_id).all()
    return [get_account_response(account) for account in accounts]


@account_router.get(
    f"{Endpoints.ACCOUNTS}/{{account_id}}",
    response_model=AccountResponse,
    summary="Get one account",
    description="Returns an account only when it belongs to the bearer-token owner.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "The bearer token is missing, invalid, or revoked."},
        status.HTTP_403_FORBIDDEN: {"description": "The requested account belongs to a different user."},
        status.HTTP_404_NOT_FOUND: {"description": "The account does not exist."},
    },
)
def get_account(
    account_id: int,
    payload: UserJWTPayload = Depends(validate_user_jwt_token),
    db: Session = Depends(get_db),
) -> AccountResponse:
    """Return an account owned by the token holder.

    Input: account ID and a valid bearer token. Output: the requested account and balance.
    """
    return get_account_response(get_owned_account(account_id, payload, db))


@account_router.patch(
    f"{Endpoints.ACCOUNTS}/{{account_id}}",
    response_model=AccountResponse,
    summary="Adjust an account balance",
    description="Deposits a positive amount or withdraws a negative amount without allowing a negative final balance.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "The bearer token is missing, invalid, or revoked."},
        status.HTTP_403_FORBIDDEN: {"description": "The requested account belongs to a different user."},
        status.HTTP_404_NOT_FOUND: {"description": "The account does not exist."},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "The amount is invalid or would make the balance negative."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "The account could not be updated."},
    },
)
def update_account_balance(
    account_id: int,
    account_update_data: AccountBalanceUpdateData,
    payload: UserJWTPayload = Depends(validate_user_jwt_token),
    db: Session = Depends(get_db),
) -> AccountResponse:
    """Adjust an account balance without allowing an overdraft.

    Input: account ID, valid bearer token, and a non-zero amount. Output: the account with its new balance.
    """
    account = get_owned_account(account_id, payload, db, lock=True)
    new_balance = account.balance + account_update_data.amount
    if new_balance < Decimal("0.00"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Insufficient account balance.")
    account.balance = new_balance
    try:
        db.commit()
        db.refresh(account)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")
    return get_account_response(account)


@account_router.delete(
    f"{Endpoints.ACCOUNTS}/{{account_id}}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an account",
    description="Deletes an account owned by the bearer-token owner, even when it has a remaining balance.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "The bearer token is missing, invalid, or revoked."},
        status.HTTP_403_FORBIDDEN: {"description": "The requested account belongs to a different user."},
        status.HTTP_404_NOT_FOUND: {"description": "The account does not exist."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "The account could not be deleted."},
    },
)
def delete_account(
    account_id: int,
    payload: UserJWTPayload = Depends(validate_user_jwt_token),
    db: Session = Depends(get_db),
) -> Response:
    """Delete an account owned by the token holder.

    Input: account ID and a valid bearer token. Output: no response body after deletion.
    """
    account = get_owned_account(account_id, payload, db)
    db.delete(account)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@account_router.post(
    Endpoints.TRANSFERS,
    status_code=status.HTTP_201_CREATED,
    response_model=TransferResponse,
    summary="Transfer funds between accounts",
    description=(
        "Atomically debits an owned source account, credits an existing different destination account, "
        "and stores the transfer note encrypted."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "The bearer token is missing, invalid, or revoked."},
        status.HTTP_403_FORBIDDEN: {"description": "The source account belongs to a different user."},
        status.HTTP_404_NOT_FOUND: {"description": "A source or destination account does not exist."},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "The amount is invalid, the accounts match, or the source balance is insufficient."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "The transfer could not be persisted."},
    },
)
def create_transfer(
    transfer_data: TransferCreateData,
    payload: UserJWTPayload = Depends(validate_user_jwt_token),
    db: Session = Depends(get_db),
) -> TransferResponse:
    """Transfer funds atomically and return the note in decrypted form.

    Input: source account ID, destination account ID, positive amount, note, and valid bearer token.
    Output: the created transfer with the note decrypted only for this response.
    """
    if transfer_data.source_account_id == transfer_data.destination_account_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Accounts must be different.")

    accounts = (
        db.query(Account)
        .filter(Account.account_id.in_([transfer_data.source_account_id, transfer_data.destination_account_id]))
        .order_by(Account.account_id)
        .with_for_update()
        .all()
    )
    accounts_by_id = {account.account_id: account for account in accounts}
    source_account = accounts_by_id.get(transfer_data.source_account_id)
    destination_account = accounts_by_id.get(transfer_data.destination_account_id)

    if not source_account or not destination_account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    if source_account.user_id != payload.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this account is forbidden.")
    if source_account.balance < transfer_data.amount:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Insufficient account balance.")

    source_account.balance -= transfer_data.amount
    destination_account.balance += transfer_data.amount
    transfer = Transfer(
        source_account_id=source_account.account_id,
        destination_account_id=destination_account.account_id,
        amount=transfer_data.amount,
        encrypted_note=encrypt_transfer_note(transfer_data.note),
    )
    db.add(transfer)
    try:
        db.commit()
        db.refresh(transfer)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")
    return TransferResponse(
        transfer_id=transfer.transfer_id,
        source_account_id=transfer.source_account_id,
        destination_account_id=transfer.destination_account_id,
        amount=transfer.amount,
        note=decrypt_transfer_note(transfer.encrypted_note),
        created_at=transfer.created_at,
    )
