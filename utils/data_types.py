"""Typed data stored in access tokens."""

from pydantic import BaseModel


class UserJWTPayload(BaseModel):
    """Data stored in a signed user access token."""

    user_id: int
    session_id: str
