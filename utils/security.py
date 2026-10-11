"""Password hashing and JWT validation utilities."""

from hashlib import sha256

from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import SecretStr
from sqlalchemy.orm import Session

from config import Settings
from src.models.token_session import TokenSession
from utils.data_types import UserJWTPayload
from utils.db import get_db


settings = Settings()
oauth2_schema = HTTPBearer()


def hash_context() -> CryptContext:
    """Create the password hashing context."""
    return CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: SecretStr) -> str:
    """Hash a password before it is stored in PostgreSQL."""
    return hash_context().hash(password.get_secret_value())


def verify_password(password: SecretStr, hashed_password: str) -> bool:
    """Compare a password with the stored hash."""
    return hash_context().verify(password.get_secret_value(), hashed_password)


def generate_user_jwt(payload: UserJWTPayload) -> str:
    """Create a signed JWT after successful user authentication."""
    return jwt.encode(payload.model_dump(), settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def get_token_fingerprint(token: str) -> str:
    """Return a one-way fingerprint used to store a token session safely."""
    return sha256(token.encode("utf-8")).hexdigest()


def encrypt_transfer_note(note: str) -> str:
    """Encrypt a transfer note before storing it in PostgreSQL."""
    cipher = Fernet(settings.NOTE_ENCRYPTION_KEY.get_secret_value().encode("utf-8"))
    return cipher.encrypt(note.encode("utf-8")).decode("utf-8")


def decrypt_transfer_note(encrypted_note: str) -> str:
    """Decrypt a transfer note before returning it to its creator."""
    cipher = Fernet(settings.NOTE_ENCRYPTION_KEY.get_secret_value().encode("utf-8"))
    return cipher.decrypt(encrypted_note.encode("utf-8")).decode("utf-8")


def validate_user_jwt_token(
    header: HTTPAuthorizationCredentials = Depends(oauth2_schema),
    db: Session = Depends(get_db),
) -> UserJWTPayload:
    """Decode a bearer token and reject missing or revoked sessions."""
    try:
        payload = UserJWTPayload(
            **jwt.decode(
                header.credentials,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
            )
        )
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT token.")

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
    return payload
