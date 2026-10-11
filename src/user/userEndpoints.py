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


@user_router.post(Endpoints.USERS, status_code=status.HTTP_201_CREATED, response_model=UserResponse)
def register_user(user_reg_data: UserRegData, db: Session = Depends(get_db)) -> UserResponse:
    """Register a user and store only a bcrypt password hash."""
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


@user_router.post(Endpoints.LOGIN, response_model=UserLoginResponse)
def login_user(user_login_data: UserLoginData, db: Session = Depends(get_db)) -> UserLoginResponse:
    """Verify credentials, issue a JWT and store its active session."""
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


@user_router.get(Endpoints.LOGIN_VALIDATION, response_model=UserResponse)
def validate_login(
    payload: UserJWTPayload = Depends(validate_user_jwt_token),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Return the public data of the authenticated user."""
    user = db.query(User).filter(User.user_id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return get_user_response(user)


@user_router.post(Endpoints.LOGOUT, status_code=status.HTTP_204_NO_CONTENT)
def logout_user(
    header: HTTPAuthorizationCredentials = Depends(oauth2_schema),
    payload: UserJWTPayload = Depends(validate_user_jwt_token),
    db: Session = Depends(get_db),
) -> Response:
    """Revoke the active JWT session."""
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


@user_router.get(f"{Endpoints.USERS}/{{user_id}}", response_model=UserResponse)
def get_user(
    user_id: int,
    payload: UserJWTPayload = Depends(validate_user_jwt_token),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Return a user's public data when requested by its owner."""
    return get_user_response(get_owned_user(user_id, payload, db))


@user_router.patch(f"{Endpoints.USERS}/{{user_id}}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_update_data: UserUpdateData,
    payload: UserJWTPayload = Depends(validate_user_jwt_token),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Update the authenticated user's address, password or both."""
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


@user_router.delete(f"{Endpoints.USERS}/{{user_id}}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    payload: UserJWTPayload = Depends(validate_user_jwt_token),
    db: Session = Depends(get_db),
) -> Response:
    """Delete the authenticated user and all related records."""
    user = get_owned_user(user_id, payload, db)
    db.delete(user)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
