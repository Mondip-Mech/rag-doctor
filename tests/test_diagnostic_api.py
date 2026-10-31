
"""Integration tests for the RAG Doctor FastAPI endpoints."""

import backend.api.diagnostics as diagnostics_api

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def make_payload() -> dict:
    """Build a valid diagnostic request."""
    return {
        "query": "What is the refund policy?",
        "generated_answer": "Refunds are available within 30 days.",
        "retrieved_chunks": [],
    }


def test_diagnostic_api_success():
    """A valid request returns the diagnostic report and metadata."""
    response = client.post(
        "/api/v1/diagnostics",
        json=make_payload(),
    )

    assert response.status_code == 200

    body = response.json()

    assert "report" in body
    assert "run_metadata" in body
    assert "agent_executions" in body
    assert "execution_events" in body
    assert "errors" in body

    report = body["report"]
    metadata = body["run_metadata"]

    assert report["run_id"] == metadata["run_id"]
    assert report["status"] == "completed"
    assert metadata["status"] == "completed"

    assert len(body["agent_executions"]) == 4
    assert len(body["execution_events"]) == 8
    assert body["errors"] == []

    assert any(
        finding["category"] == "retrieval_miss"
        for finding in report["findings"]
    )


def test_diagnostic_api_rejects_invalid_request():
    """Invalid Pydantic input returns a sanitized HTTP 422."""
    payload = make_payload()
    payload["query"] = ""

    response = client.post(
        "/api/v1/diagnostics",
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Invalid request payload. Please check the API schema."
    )


def test_diagnostic_api_handles_workflow_exception(monkeypatch):
    """Unexpected workflow errors return a safe HTTP 500."""

    def failing_workflow(request):
        raise RuntimeError("Sensitive internal failure details")

    monkeypatch.setattr(
        diagnostics_api,
        "run_diagnostic",
        failing_workflow,
    )

    response = client.post(
        "/api/v1/diagnostics",
        json=make_payload(),
    )

    assert response.status_code == 500

    detail = response.json()["detail"]

    assert detail == (
        "Diagnostic execution failed. Please retry later."
    )

    assert "Sensitive internal failure details" not in response.text
    assert "Traceback" not in response.text
