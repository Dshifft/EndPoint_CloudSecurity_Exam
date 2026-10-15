"""FastAPI application entry point for the banking service."""

from collections.abc import Awaitable, Callable
import logging
import os

import fastapi
from azure.monitor.opentelemetry import configure_azure_monitor

from src.models import Account, TokenSession, Transfer, User
from src.account.accountEndpoints import account_router
from src.user.userEndpoints import user_router
from utils.db import Base, Engine


LOGGER_NAME = "banking_api"
logger = logging.getLogger(LOGGER_NAME)

if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    configure_azure_monitor(logger_name=LOGGER_NAME)


banking_app = fastapi.FastAPI(
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
    logger.info("database_tables_ready")


@banking_app.middleware("http")
async def log_request(
    request: fastapi.Request,
    call_next: Callable[[fastapi.Request], Awaitable[fastapi.Response]],
) -> fastapi.Response:
    """Record request metadata without logging query values or request bodies."""
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "http_request_failed method=%s path=%s",
            request.method,
            request.url.path,
        )
        raise

    logger.info(
        "http_request_completed method=%s path=%s status_code=%s",
        request.method,
        request.url.path,
        response.status_code,
    )
    return response


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
