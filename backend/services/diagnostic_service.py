
"""Service layer for executing RAG Doctor diagnostics."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, cast

from backend.api.schemas import DiagnosticRequest
from backend.graph.state import (
    RAGDoctorState,
    create_initial_state,
)
from backend.graph.workflow import build_diagnostic_graph


@lru_cache(maxsize=1)
def get_diagnostic_graph() -> Any:
    """Return a cached compiled LangGraph workflow."""
    return build_diagnostic_graph()


def run_diagnostic(
    request: DiagnosticRequest,
) -> RAGDoctorState:
    """Execute the diagnostic workflow for one request.

    Each invocation receives an isolated initial state.
    The compiled graph can be reused across requests.
    """
    initial_state = create_initial_state(
        request=request,
        model_provider="none",
    )

    graph = get_diagnostic_graph()
    result = graph.invoke(initial_state)

    if result.get("final_report") is None:
        raise RuntimeError(
            "Diagnostic workflow did not produce a final report."
        )

    return cast(RAGDoctorState, result)
