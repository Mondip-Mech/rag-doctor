
"""FastAPI routes for RAG Doctor diagnostics."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from backend.api.responses import DiagnosticAPIResponse
from backend.api.schemas import DiagnosticRequest
from backend.services.diagnostic_service import run_diagnostic


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1",
    tags=["Diagnostics"],
)


@router.post(
    "/diagnostics",
    response_model=DiagnosticAPIResponse,
)
def create_diagnostic(
    request: DiagnosticRequest,
) -> DiagnosticAPIResponse:
    """Accept a diagnostic request and execute the RAG workflow."""

    try:
        result = run_diagnostic(request)

        report = result.get("final_report")

        if report is None:
            raise RuntimeError(
                "Diagnostic workflow returned no final report."
            )

        return DiagnosticAPIResponse(
            report=report,
            run_metadata=result["run_metadata"],
            agent_executions=result["agent_executions"],
            execution_events=result["execution_events"],
            errors=result["errors"],
        )

    except Exception:
        # Keep internal exception details out of the HTTP response.
        logger.error(
            "Diagnostic execution failed for run_id=%s",
            request.run_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Diagnostic execution failed. Please retry later.",
        ) from None
