
import threading

import pytest

import backend.graph.workflow as workflow





from datetime import datetime, timezone

from backend.api.schemas import (
    AgentError,
    AgentFinding,
    AgentName,
    DiagnosticRequest,
    FindingCategory,
    FindingSeverity,
)
from backend.graph.state import create_initial_state
from backend.graph.workflow import build_diagnostic_graph


def make_finding(
    agent: AgentName,
    category: FindingCategory,
    summary: str,
) -> AgentFinding:
    return AgentFinding(
        agent=agent,
        category=category,
        severity=FindingSeverity.HIGH,
        summary=summary,
        details=f"Test details for {summary}",
        confidence=0.9,
        evidence_basis="inference",
        recommendations=["Inspect the relevant pipeline stage"],
    )


def make_state():
    request = DiagnosticRequest(
        query="What is the refund policy?",
        generated_answer="Refunds are always available.",
        retrieved_chunks=[],
    )
    return create_initial_state(request)


def test_workflow_generates_final_report():
    graph = build_diagnostic_graph()
    result = graph.invoke(make_state())

    report = result["final_report"]

    assert report is not None
    assert report.run_id == result["run_metadata"].run_id
    assert report.status in {"completed", "partial", "failed"}
    assert result["run_metadata"].finished_at is not None
    assert result["run_metadata"].duration_ms is not None


def test_aggregator_preserves_findings_from_multiple_nodes():
    from backend.graph.workflow import aggregate_report

    state = make_state()
    state["findings"] = [
        make_finding(
            AgentName.RETRIEVAL_AUDITOR,
            FindingCategory.RETRIEVAL_MISS,
            "No retrieved chunks were returned",
        ),
        make_finding(
            AgentName.GENERATION_AUDITOR,
            FindingCategory.GENERATION_ERROR,
            "Answer may be problematic",
        ),
    ]

    result = aggregate_report(state)
    report = result["final_report"]

    assert len(report.findings) == 2
    assert {
        finding.agent for finding in report.findings
    } == {
        AgentName.RETRIEVAL_AUDITOR,
        AgentName.GENERATION_AUDITOR,
    }
    assert report.primary_hypothesis is not None
    assert report.primary_hypothesis.category in {
        FindingCategory.RETRIEVAL_MISS,
        FindingCategory.GENERATION_ERROR,
    }


def test_aggregator_marks_partial_when_findings_and_errors_exist():
    from backend.graph.workflow import aggregate_report

    state = make_state()
    state["findings"] = [
        make_finding(
            AgentName.RETRIEVAL_AUDITOR,
            FindingCategory.RETRIEVAL_MISS,
            "No retrieved chunks were returned",
        )
    ]
    state["errors"] = [
        AgentError(
            node_name="context_auditor",
            agent=AgentName.CONTEXT_AUDITOR,
            error_code="TEST_ERROR",
            message="Simulated node failure",
            retryable=False,
            correlation_id=state["run_metadata"].run_id,
        )
    ]

    result = aggregate_report(state)

    assert result["final_report"].status == "partial"
    assert result["run_metadata"].status == "partial"
    assert len(result["final_report"].findings) == 1


def test_aggregator_marks_failed_when_errors_exist_without_findings():
    from backend.graph.workflow import aggregate_report

    state = make_state()
    state["errors"] = [
        AgentError(
            node_name="retrieval_auditor",
            agent=AgentName.RETRIEVAL_AUDITOR,
            error_code="TEST_ERROR",
            message="Simulated node failure",
            retryable=False,
            correlation_id=state["run_metadata"].run_id,
        )
    ]

    result = aggregate_report(state)

    assert result["final_report"].status == "failed"
    assert result["final_report"].primary_hypothesis is None




def test_four_specialists_reach_barrier_concurrently(monkeypatch):
    """Prove all four branches overlap without relying on elapsed time."""
    barrier = threading.Barrier(4, timeout=5)
    reached = set()
    lock = threading.Lock()

    original_nodes = {
        "retrieval_auditor": workflow.retrieval_auditor,
        "context_auditor": workflow.context_auditor,
        "grounding_auditor": workflow.grounding_auditor,
        "generation_auditor": workflow.generation_auditor,
    }

    def make_concurrent_node(name, original):
        def concurrent_node(state):
            with lock:
                reached.add(name)

            # All four calls must arrive before any can continue.
            barrier.wait()
            return original(state)

        return concurrent_node

    for name, original in original_nodes.items():
        monkeypatch.setattr(
            workflow,
            name,
            make_concurrent_node(name, original),
        )

    result = workflow.build_diagnostic_graph().invoke(make_state())

    assert reached == set(original_nodes)
    assert result["errors"] == []
    assert len(result["agent_executions"]) == 4
    assert all(
        record.status == "completed"
        for record in result["agent_executions"]
    )


def test_unexpected_specialist_exception_preserves_other_results(
    monkeypatch,
):
    """An exception outside execute_specialist must not abort the graph."""

    def exploding_node(state):
        raise RuntimeError("deliberately injected test failure")

    monkeypatch.setattr(workflow, "context_auditor", exploding_node)

    result = workflow.build_diagnostic_graph().invoke(make_state())

    assert result["final_report"] is not None
    assert result["final_report"].status == "partial"
    assert result["run_metadata"].status == "partial"

    assert len(result["errors"]) == 1
    error = result["errors"][0]
    assert error.node_name == "context_auditor"
    assert error.error_code == "RuntimeError"
    assert error.correlation_id == result["run_metadata"].run_id
    assert "deliberately injected" not in error.message

    executions = {
        record.agent: record
        for record in result["agent_executions"]
    }
    assert len(executions) == 4
    assert executions[AgentName.CONTEXT_AUDITOR].status == "failed"

    for agent in (
        AgentName.RETRIEVAL_AUDITOR,
        AgentName.GROUNDING_AUDITOR,
        AgentName.GENERATION_AUDITOR,
    ):
        assert executions[agent].status == "completed"

    # Successful auditors still produce results. In this fixture,
    # the retrieval auditor finds that no chunks were retrieved.
    assert any(
        finding.agent == AgentName.RETRIEVAL_AUDITOR
        for finding in result["findings"]
    )

    events = result["execution_events"]
    context_events = [
        event for event in events
        if event.agent == AgentName.CONTEXT_AUDITOR
    ]
    assert [event.event_type for event in sorted(
        context_events, key=lambda event: event.timestamp
    )] == ["started", "failed"]

    assert result["run_metadata"].finished_at is not None
    assert result["run_metadata"].duration_ms is not None
    assert result["run_metadata"].duration_ms >= 0
    assert result["final_report"].run_id == result["run_metadata"].run_id


def test_root_cause_selection_is_independent_of_finding_order():
    """Fixed finding IDs make tie-breaking reproducible."""
    from backend.graph.workflow import _build_primary_hypothesis

    retrieval = make_finding(
        AgentName.RETRIEVAL_AUDITOR,
        FindingCategory.RETRIEVAL_MISS,
        "Retrieval missed relevant content",
    ).model_copy(update={"finding_id": "finding-retrieval-001"})

    generation = make_finding(
        AgentName.GENERATION_AUDITOR,
        FindingCategory.GENERATION_ERROR,
        "Generation returned a problematic answer",
    ).model_copy(update={"finding_id": "finding-generation-001"})

    first = _build_primary_hypothesis([retrieval, generation])
    second = _build_primary_hypothesis([generation, retrieval])

    assert first is not None
    assert second is not None
    assert first.category == second.category
    assert first.supporting_finding_ids == second.supporting_finding_ids
    assert first.confidence == second.confidence


def test_execution_events_and_records_are_consistent():
    result = workflow.build_diagnostic_graph().invoke(make_state())

    assert len(result["agent_executions"]) == 4

    for record in result["agent_executions"]:
        assert record.started_at is not None
        assert record.finished_at is not None
        assert record.finished_at >= record.started_at
        assert record.duration_ms is not None
        assert record.duration_ms >= 0

        events = [
            event for event in result["execution_events"]
            if event.agent == record.agent
        ]
        events.sort(key=lambda event: event.timestamp)

        assert len(events) == 2
        assert events[0].event_type == "started"
        assert events[1].event_type == (
            "failed" if record.status == "failed" else "completed"
        )

    report = result["final_report"]
    metadata = result["run_metadata"]

    assert report.run_id == metadata.run_id
    assert report.status == metadata.status
    assert metadata.finished_at is not None
    assert metadata.duration_ms is not None
    assert metadata.duration_ms >= 0
