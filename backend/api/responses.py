
"""API response contracts for RAG Doctor."""

from pydantic import Field

from backend.api.schemas import (
    AgentError,
    AgentExecutionRecord,
    DiagnosticReport,
    ExecutionEvent,
    RunMetadata,
    StrictModel,
)


class DiagnosticAPIResponse(StrictModel):
    """Complete HTTP response for a diagnostic execution."""

    report: DiagnosticReport

    run_metadata: RunMetadata

    agent_executions: list[AgentExecutionRecord] = Field(
        default_factory=list
    )

    execution_events: list[ExecutionEvent] = Field(
        default_factory=list
    )

    errors: list[AgentError] = Field(
        default_factory=list
    )
