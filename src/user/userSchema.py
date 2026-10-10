"""Request and response schemas for user and authentication endpoints."""

from pydantic import BaseModel, EmailStr, SecretStr


class UserRegData(BaseModel):
    """Data required to register a user."""

    name: str
    address: str
    email: EmailStr
    password: SecretStr


class UserLoginData(BaseModel):
    """Credentials required to start a session."""

    email: EmailStr
    password: SecretStr


class UserUpdateData(BaseModel):
    """Personal data a user is allowed to update."""

    address: str | None = None
    password: SecretStr | None = None


class UserResponse(BaseModel):
    """Public user data returned by the API."""

    user_id: int
    name: str
    address: str
    email: EmailStr


class UserLoginResponse(BaseModel):
    """Bearer token returned after a successful login."""

    access_token: str
    token_type: str = "bearer"
