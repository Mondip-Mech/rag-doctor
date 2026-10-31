from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from backend.api.schemas import (
    AgentError,
    AgentExecutionRecord,
    AgentFinding,
    DiagnosticReport,
    DiagnosticRequest,
    ExecutionEvent,
    RegressionTestCase,
    RegressionTestResult,
    RootCauseHypothesis,
    RunMetadata,
)


# ============================================================
# 1. SHARED LANGGRAPH STATE
# ============================================================

class RAGDoctorState(TypedDict):
    """
    Shared state for the RAG Doctor multi-agent workflow.

    Single-writer fields:
        request
        run_metadata
        final_report

    Append-only fields:
        findings
        root_cause_hypotheses
        regression_test_cases
        regression_test_results
        agent_executions
        execution_events
        errors
    """

    # Original diagnostic input.
    request: DiagnosticRequest

    # Information about the current diagnostic run.
    run_metadata: RunMetadata

    # Results from parallel diagnostic agents.
    findings: Annotated[
        list[AgentFinding],
        operator.add,
    ]

    # Root-cause analysis results.
    root_cause_hypotheses: Annotated[
        list[RootCauseHypothesis],
        operator.add,
    ]

    # Regression testing.
    regression_test_cases: Annotated[
        list[RegressionTestCase],
        operator.add,
    ]

    regression_test_results: Annotated[
        list[RegressionTestResult],
        operator.add,
    ]

    # Agent execution tracking.
    agent_executions: Annotated[
        list[AgentExecutionRecord],
        operator.add,
    ]

    # Chronological workflow events.
    execution_events: Annotated[
        list[ExecutionEvent],
        operator.add,
    ]

    # Structured errors.
    errors: Annotated[
        list[AgentError],
        operator.add,
    ]

    # Produced by the final reporting node.
    final_report: DiagnosticReport | None


# ============================================================
# 2. INITIAL STATE FACTORY
# ============================================================

def create_initial_state(
    request: DiagnosticRequest,
    app_version: str = "0.1.0",
    model_provider: str = "ollama",
) -> RAGDoctorState:
    """
    Creates a fresh, isolated state for every diagnostic run.

    All append-only collections start empty.
    """

    metadata = RunMetadata(
        run_id=request.run_id,
        status="pending",
        app_version=app_version,
        model_name=request.model_name,
        model_provider=model_provider,
    )

    return {
        "request": request,
        "run_metadata": metadata,
        "findings": [],
        "root_cause_hypotheses": [],
        "regression_test_cases": [],
        "regression_test_results": [],
        "agent_executions": [],
        "execution_events": [],
        "errors": [],
        "final_report": None,
    }