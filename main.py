"""FastAPI application entry point for the banking service."""

from fastapi import FastAPI

from src.models import Account, TokenSession, Transfer, User
from src.account.accountEndpoints import account_router
from src.user.userEndpoints import user_router
from utils.db import Base, Engine


banking_app = FastAPI(
    title="Banking API",
    description=(
        "REST API for user authentication, user-owned accounts, balance adjustments, "
        "and encrypted transfer notes. Protected endpoints require a bearer JWT."
    ),
    version="0.1.0",
    docs_url="/mc101-docs",
    redoc_url=None,
)

banking_app.include_router(user_router)
banking_app.include_router(account_router)


@banking_app.on_event("startup")
def create_database_tables() -> None:
    """Create the database tables when the API starts."""
    Base.metadata.create_all(bind=Engine)


@banking_app.get(
    "/health",
    tags=["health"],
    summary="Check service health",
    description="Returns a confirmation that the service is running.",
    response_description="Service health status.",
)
def health() -> dict[str, str]:
    """Confirm that the service is available.

    Input: none. Output: the current service status.
    """
    return {"status": "ok"}
