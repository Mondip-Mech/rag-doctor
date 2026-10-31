
"""LangGraph workflow for deterministic RAG diagnostics."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from langgraph.graph import END, START, StateGraph

from backend.api.schemas import (
    AgentError,
    AgentExecutionRecord,
    AgentName,
    DiagnosticReport,
    ExecutionEvent,
    FindingCategory,
    FindingSeverity,
    RootCauseHypothesis,
)
from backend.graph.nodes import (
    context_auditor,
    generation_auditor,
    grounding_auditor,
    retrieval_auditor,
)
from backend.graph.state import RAGDoctorState


SEVERITY_RANK = {
    FindingSeverity.CRITICAL: 4,
    FindingSeverity.HIGH: 3,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.LOW: 1,
}

CATEGORY_ORDER = {
    category: index
    for index, category in enumerate(FindingCategory)
}


def mark_run_started(state: RAGDoctorState) -> dict[str, object]:
    """Mark the run as active before parallel execution."""
    metadata = state["run_metadata"].model_copy(
        update={
            "status": "running",
            "finished_at": None,
            "duration_ms": None,
        }
    )
    return {"run_metadata": metadata}


def _guard_specialist(
    node_name: str,
    agent: AgentName,
    node: Callable,
) -> Callable:
    """Convert unexpected specialist-node exceptions into state updates."""

    def guarded_node(state: RAGDoctorState) -> dict[str, object]:
        started_at = datetime.now(timezone.utc)

        try:
            return node(state)
        except Exception as exc:
            finished_at = datetime.now(timezone.utc)
            duration_ms = max(
                0.0,
                (finished_at - started_at).total_seconds() * 1000,
            )
            error_type = type(exc).__name__
            run_id = state["request"].run_id

            error = AgentError(
                node_name=node_name,
                agent=agent,
                error_code=error_type,
                message=f"{node_name} failed with {error_type}.",
                retryable=False,
                correlation_id=run_id,
                occurred_at=finished_at,
            )

            execution = AgentExecutionRecord(
                agent=agent,
                status="failed",
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                output_finding_ids=[],
            )

            events = [
                ExecutionEvent(
                    node_name=node_name,
                    agent=agent,
                    event_type="started",
                    timestamp=started_at,
                    detail="Specialist node started.",
                ),
                ExecutionEvent(
                    node_name=node_name,
                    agent=agent,
                    event_type="failed",
                    timestamp=finished_at,
                    duration_ms=duration_ms,
                    detail=f"Unexpected node exception: {error_type}.",
                ),
            ]

            # These are new values only. The state reducers append them
            # to outputs from other branches without overwriting them.
            return {
                "findings": [],
                "agent_executions": [execution],
                "execution_events": events,
                "errors": [error],
            }

    guarded_node.__name__ = f"guarded_{node_name}"
    return guarded_node


def _build_primary_hypothesis(
    findings: list,
) -> RootCauseHypothesis | None:
    """Select a leading hypothesis using stable ranking rules."""
    if not findings:
        return None

    ranked = sorted(
        findings,
        key=lambda finding: (
            -SEVERITY_RANK[finding.severity],
            -finding.confidence,
            CATEGORY_ORDER[finding.category],
            finding.finding_id,
        ),
    )

    primary = ranked[0]
    supporting = [
        finding
        for finding in ranked
        if finding.category == primary.category
    ]

    confidence = sum(
        finding.confidence for finding in supporting
    ) / len(supporting)

    actions: list[str] = []
    for finding in supporting:
        for recommendation in finding.recommendations:
            if recommendation not in actions:
                actions.append(recommendation)

    return RootCauseHypothesis(
        category=primary.category,
        explanation=(
            f"Leading diagnostic hypothesis: {primary.summary} "
            f"Supporting findings in this category: {len(supporting)}. "
            "This is a deterministic rule-based hypothesis, "
            "not proof of causality."
        ),
        confidence=round(confidence, 4),
        supporting_finding_ids=[
            finding.finding_id for finding in supporting
        ],
        recommended_actions=actions[:20],
    )


def aggregate_report(
    state: RAGDoctorState,
) -> dict[str, object]:
    """Consolidate branch results and finalize metadata."""
    now = datetime.now(timezone.utc)
    metadata = state["run_metadata"]

    findings = sorted(
        state["findings"],
        key=lambda finding: (
            -SEVERITY_RANK[finding.severity],
            -finding.confidence,
            CATEGORY_ORDER[finding.category],
            finding.finding_id,
        ),
    )

    errors = state["errors"]

    if errors and findings:
        status = "partial"
    elif errors:
        status = "failed"
    else:
        status = "completed"

    recommendations: list[str] = []
    for finding in findings:
        for recommendation in finding.recommendations:
            if recommendation not in recommendations:
                recommendations.append(recommendation)

    limitations = [
        "Rule-based diagnostics are heuristic and do not prove causality.",
        "Grounding checks do not establish semantic entailment.",
        "No LLM-based verification was performed.",
    ]

    if errors:
        limitations.append(
            f"{len(errors)} diagnostic node error(s) occurred; "
            "the report may be incomplete."
        )

    if not findings:
        limitations.append(
            "No findings were produced; absence of findings does not "
            "prove the RAG pipeline is correct."
        )

    report = DiagnosticReport(
        run_id=metadata.run_id,
        status=status,
        summary=(
            f"Diagnostic run {metadata.run_id}: "
            f"{len(findings)} finding(s), {len(errors)} error(s). "
            f"Overall status: {status}."
        ),
        primary_hypothesis=_build_primary_hypothesis(findings),
        findings=findings,
        recommendations=recommendations,
        regression_test_ids=[],
        limitations=limitations,
    )

    duration_ms = max(
        0.0,
        (now - metadata.created_at).total_seconds() * 1000,
    )

    finalized_metadata = metadata.model_copy(
        update={
            "status": status,
            "finished_at": now,
            "duration_ms": duration_ms,
        }
    )

    return {
        "final_report": report,
        "run_metadata": finalized_metadata,
    }


def build_diagnostic_graph():
    """Compile the four-branch parallel diagnostic workflow."""
    builder = StateGraph(RAGDoctorState)

    specialists = (
        (
            "retrieval_auditor",
            AgentName.RETRIEVAL_AUDITOR,
            retrieval_auditor,
        ),
        (
            "context_auditor",
            AgentName.CONTEXT_AUDITOR,
            context_auditor,
        ),
        (
            "grounding_auditor",
            AgentName.GROUNDING_AUDITOR,
            grounding_auditor,
        ),
        (
            "generation_auditor",
            AgentName.GENERATION_AUDITOR,
            generation_auditor,
        ),
    )

    builder.add_node("mark_run_started", mark_run_started)

    for node_name, agent, node in specialists:
        builder.add_node(
            node_name,
            _guard_specialist(node_name, agent, node),
        )

    builder.add_node("aggregate_report", aggregate_report)
    builder.add_edge(START, "mark_run_started")

    for node_name, _, _ in specialists:
        builder.add_edge("mark_run_started", node_name)
        builder.add_edge(node_name, "aggregate_report")

    builder.add_edge("aggregate_report", END)

    return builder.compile()
