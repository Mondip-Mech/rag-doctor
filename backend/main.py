
"""FastAPI application entry point for RAG Doctor."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.api.diagnostics import router as diagnostics_router


logger = logging.getLogger(__name__)

app = FastAPI(
    title="RAG Doctor API",
    description="Deterministic diagnostics for Retrieval-Augmented Generation systems.",
    version="0.1.0",
)


# Register diagnostic routes.
app.include_router(diagnostics_router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """Return basic API availability."""
    return {"status": "ok"}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return a sanitized validation error without echoing input values."""
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Invalid request payload. Please check the API schema."
        },
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Prevent internal exception details from reaching API clients."""
    logger.exception(
        "Unhandled API exception on path %s",
        request.url.path,
    )

    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred."},
    )
