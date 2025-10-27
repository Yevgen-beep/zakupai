"""
Centralized exception handlers for risk-engine.
Stage 7 Phase 1: Security Quick Wins
"""

from typing import Any
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
import logging

log = logging.getLogger("risk-engine")


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Centralized handler for Pydantic validation errors (422).
    Returns standardized error format.
    """
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        errors.append({"field": field, "message": message, "type": error["type"]})

    log.warning(
        f"Validation error on {request.url.path}: {len(errors)} error(s)",
        extra={"errors": errors}
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": errors,
        },
    )


async def payload_too_large_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handler for payload size limit exceeded (413).
    """
    log.warning(
        f"Payload too large on {request.url.path}",
        extra={"client": request.client.host if request.client else None}
    )

    return JSONResponse(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        content={"detail": "Payload Too Large"},
    )


async def rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handler for rate limit exceeded (429).
    """
    log.warning(
        f"Rate limit exceeded on {request.url.path}",
        extra={"client": request.client.host if request.client else None}
    )

    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": "Too Many Requests",
            "message": "Rate limit exceeded. Please try again later."
        },
    )


async def unauthorized_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handler for unauthorized access (401).
    """
    log.warning(
        f"Unauthorized access attempt on {request.url.path}",
        extra={"client": request.client.host if request.client else None}
    )

    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Unauthorized"},
    )
