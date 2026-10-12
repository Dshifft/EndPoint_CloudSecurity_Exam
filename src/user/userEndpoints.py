"""User registration, authentication and account-management endpoints."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from src.models.token_session import TokenSession
from src.models.user import User
from src.user.userSchema import UserLoginData, UserLoginResponse, UserRegData, UserResponse, UserUpdateData
from utils.constants import Endpoints
from utils.data_types import UserJWTPayload
from utils.db import get_db
from utils.security import (
    generate_user_jwt,
    get_token_fingerprint,
    hash_password,
    oauth2_schema,
    validate_user_jwt_token,
    verify_password,
)


user_router = APIRouter(tags=["users"])


def get_user_response(user: User) -> UserResponse:
    """Build a response without exposing the password hash."""
    return UserResponse(
        user_id=user.user_id,
        name=user.name,
        address=user.address,
        email=user.email,
    )


def get_owned_user(user_id: int, payload: UserJWTPayload, db: Session) -> User:
    """Return the requested user only when it belongs to the token holder."""
    if user_id != payload.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this user is forbidden.")
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


@user_router.post(
    Endpoints.USERS,
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    summary="Register a user",
    description="Creates a user from name, address, email, and password. The password is stored only as a bcrypt hash.",
    responses={
        status.HTTP_409_CONFLICT: {"description": "The email address is already registered."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "The user could not be persisted."},
    },
)
def register_user(user_reg_data: UserRegData, db: Session = Depends(get_db)) -> UserResponse:
    """Register a user and return its public data.

    Input: name, address, email, and password. Output: public user data without the password hash.
    """
    existing_user = db.query(User).filter(User.email == str(user_reg_data.email)).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists.")

    user = User(
        name=user_reg_data.name,
        address=user_reg_data.address,
        email=str(user_reg_data.email),
        hashed_password=hash_password(user_reg_data.password),
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists.")
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")
    return get_user_response(user)


@user_router.post(
    Endpoints.LOGIN,
    response_model=UserLoginResponse,
    summary="Authenticate a user",
    description="Checks an email and password, then creates an active JWT session.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "The email or password is invalid."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "The login session could not be stored."},
    },
)
def login_user(user_login_data: UserLoginData, db: Session = Depends(get_db)) -> UserLoginResponse:
    """Authenticate credentials and return a bearer token.

    Input: email and password. Output: a JWT access token for protected endpoints.
    """
    user = db.query(User).filter(User.email == str(user_login_data.email)).first()
    if not user or not verify_password(user_login_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    token = generate_user_jwt(UserJWTPayload(user_id=user.user_id, session_id=str(uuid4())))
    session = TokenSession(user_id=user.user_id, token_fingerprint=get_token_fingerprint(token))
    db.add(session)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")
    return UserLoginResponse(access_token=token)


@user_router.get(
    Endpoints.LOGIN_VALIDATION,
    response_model=UserResponse,
    summary="Validate the active login",
    description="Returns the public user data associated with a valid, non-revoked bearer token.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "The bearer token is missing, invalid, or revoked."},
        status.HTTP_404_NOT_FOUND: {"description": "The user no longer exists."},
    },
)
def validate_login(
    payload: UserJWTPayload = Depends(validate_user_jwt_token),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Return public data for the active token holder.

    Input: a valid bearer token. Output: the authenticated user's public data.
    """
    user = db.query(User).filter(User.user_id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return get_user_response(user)


@user_router.post(
    Endpoints.LOGOUT,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out the active session",
    description="Revokes the bearer token session so it cannot access protected endpoints again.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "The bearer token is missing, invalid, or already revoked."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "The session could not be revoked."},
    },
)
def logout_user(
    header: HTTPAuthorizationCredentials = Depends(oauth2_schema),
    payload: UserJWTPayload = Depends(validate_user_jwt_token),
    db: Session = Depends(get_db),
) -> Response:
    """Revoke the session associated with the bearer token.

    Input: a valid bearer token. Output: no response body when the session is revoked.
    """
    session = (
        db.query(TokenSession)
        .filter(
            TokenSession.user_id == payload.user_id,
            TokenSession.token_fingerprint == get_token_fingerprint(header.credentials),
            TokenSession.is_revoked.is_(False),
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT token.")
    session.is_revoked = True
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@user_router.get(
    f"{Endpoints.USERS}/{{user_id}}",
    response_model=UserResponse,
    summary="Get one user",
    description="Returns public data only when the requested user ID belongs to the bearer-token owner.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "The bearer token is missing, invalid, or revoked."},
        status.HTTP_403_FORBIDDEN: {"description": "The requested user belongs to a different account."},
        status.HTTP_404_NOT_FOUND: {"description": "The user does not exist."},
    },
)
def get_user(
    user_id: int,
    payload: UserJWTPayload = Depends(validate_user_jwt_token),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Return public data for a user owned by the token holder.

    Input: user ID and a valid bearer token. Output: the requested user's public data.
    """
    return get_user_response(get_owned_user(user_id, payload, db))


@user_router.patch(
    f"{Endpoints.USERS}/{{user_id}}",
    response_model=UserResponse,
    summary="Update one user",
    description="Updates the address, password, or both for the bearer-token owner. Name and email cannot be changed.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "The bearer token is missing, invalid, or revoked."},
        status.HTTP_403_FORBIDDEN: {"description": "The requested user belongs to a different account."},
        status.HTTP_404_NOT_FOUND: {"description": "The user does not exist."},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "No address or password was supplied."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "The user could not be updated."},
    },
)
def update_user(
    user_id: int,
    user_update_data: UserUpdateData,
    payload: UserJWTPayload = Depends(validate_user_jwt_token),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Update mutable personal data for the token holder.

    Input: user ID, valid bearer token, and address, password, or both. Output: updated public user data.
    """
    user = get_owned_user(user_id, payload, db)
    if user_update_data.address is None and user_update_data.password is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="No update data was supplied.")
    if user_update_data.address is not None:
        user.address = user_update_data.address
    if user_update_data.password is not None:
        user.hashed_password = hash_password(user_update_data.password)
    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")
    return get_user_response(user)


@user_router.delete(
    f"{Endpoints.USERS}/{{user_id}}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one user",
    description="Deletes the bearer-token owner and its related accounts, sessions, and transfers.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "The bearer token is missing, invalid, or revoked."},
        status.HTTP_403_FORBIDDEN: {"description": "The requested user belongs to a different account."},
        status.HTTP_404_NOT_FOUND: {"description": "The user does not exist."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "The user could not be deleted."},
    },
)
def delete_user(
    user_id: int,
    payload: UserJWTPayload = Depends(validate_user_jwt_token),
    db: Session = Depends(get_db),
) -> Response:
    """Delete a user owned by the token holder.

    Input: user ID and a valid bearer token. Output: no response body after deletion.
    """
    user = get_owned_user(user_id, payload, db)
    db.delete(user)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
