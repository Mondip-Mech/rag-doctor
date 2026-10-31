from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ============================================================
# 1. BASE MODEL
# ============================================================

class StrictModel(BaseModel):
    """
    Base class for all RAG Doctor data contracts.

    - Rejects unexpected fields.
    - Strips surrounding whitespace from strings.
    - Validates assignments.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


# ============================================================
# 2. ENUMS
# ============================================================

class AgentName(str, Enum):
    RETRIEVAL_AUDITOR = "retrieval_auditor"
    CONTEXT_AUDITOR = "context_auditor"
    GROUNDING_AUDITOR = "grounding_auditor"
    GENERATION_AUDITOR = "generation_auditor"
    ROOT_CAUSE_COORDINATOR = "root_cause_coordinator"
    REGRESSION_TEST_GENERATOR = "regression_test_generator"
    VERIFICATION_AGENT = "verification_agent"


class FindingCategory(str, Enum):
    RETRIEVAL_MISS = "retrieval_miss"
    LOW_RELEVANCE = "low_relevance"
    CONTEXT_TRUNCATION = "context_truncation"
    DUPLICATE_CONTEXT = "duplicate_context"
    CONTEXT_CONFLICT = "context_conflict"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    CITATION_MISMATCH = "citation_mismatch"
    QUERY_MISINTERPRETATION = "query_misinterpretation"
    GENERATION_ERROR = "generation_error"
    UNKNOWN = "unknown"


class FindingSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================
# 3. INPUT DATA CONTRACTS
# ============================================================

class RetrievedChunk(StrictModel):
    """Represents one document returned by a retriever."""

    chunk_id: str = Field(min_length=1, max_length=200)

    content: str = Field(
        min_length=1,
        max_length=20_000,
    )

    score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    rank: int | None = Field(
        default=None,
        ge=1,
    )

    source: str | None = None

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class DiagnosticRequest(StrictModel):
    """
    Complete input supplied to the RAG diagnostic workflow.
    """

    run_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    query: str = Field(
        min_length=1,
        max_length=10_000,
    )

    generated_answer: str = Field(
        default="",
        max_length=30_000,
    )

    expected_answer: str | None = Field(
        default=None,
        max_length=30_000,
    )

    retrieved_chunks: list[RetrievedChunk] = Field(
        default_factory=list,
        max_length=200,
    )

    assembled_context: str | None = Field(
        default=None,
        max_length=100_000,
    )

    model_name: str | None = None

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_unique_chunk_ids(self):
        chunk_ids = [
            chunk.chunk_id
            for chunk in self.retrieved_chunks
        ]

        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError(
                "Retrieved chunk IDs must be unique."
            )

        return self


# ============================================================
# 4. EVIDENCE CONTRACTS
# ============================================================

class EvidenceReference(StrictModel):
    """
    Identifies the source supporting an agent's finding.
    """

    source_type: Literal[
        "query",
        "retrieved_chunk",
        "assembled_context",
        "generated_answer",
        "expected_answer",
    ]

    source_id: str = Field(min_length=1)

    excerpt: str | None = Field(
        default=None,
        max_length=2_000,
    )

    rationale: str | None = Field(
        default=None,
        max_length=1_000,
    )


# ============================================================
# 5. AGENT FINDINGS
# ============================================================

class AgentFinding(StrictModel):
    """
    Structured diagnostic result from one specialist agent.
    """

    finding_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    agent: AgentName

    category: FindingCategory

    severity: FindingSeverity

    summary: str = Field(
        min_length=1,
        max_length=1_000,
    )

    details: str = Field(
        min_length=1,
        max_length=5_000,
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    evidence_basis: Literal[
        "direct_evidence",
        "inference",
    ] = "inference"

    evidence: list[EvidenceReference] = Field(
        default_factory=list,
        max_length=50,
    )

    recommendations: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_evidence(self):
        if (
            self.evidence_basis == "direct_evidence"
            and not self.evidence
        ):
            raise ValueError(
                "Direct evidence findings must include "
                "at least one evidence reference."
            )

        return self


# ============================================================
# 6. ROOT CAUSE HYPOTHESES
# ============================================================

class RootCauseHypothesis(StrictModel):

    hypothesis_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    category: FindingCategory

    explanation: str = Field(
        min_length=1,
        max_length=5_000,
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    supporting_finding_ids: list[str] = Field(
        default_factory=list,
    )

    contradicting_finding_ids: list[str] = Field(
        default_factory=list,
    )

    recommended_actions: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_finding_references(self):

        supporting = set(self.supporting_finding_ids)
        contradicting = set(self.contradicting_finding_ids)

        if supporting & contradicting:
            raise ValueError(
                "A finding cannot both support and "
                "contradict the same hypothesis."
            )

        return self


# ============================================================
# 7. REGRESSION TEST CONTRACTS
# ============================================================

class RegressionAssertion(StrictModel):

    kind: Literal[
        "required_chunk_present",
        "answer_contains",
        "answer_excludes",
        "expected_answer_supported",
        "no_unsupported_claims",
    ]

    target: str | None = None

    description: str = Field(
        min_length=1,
        max_length=500,
    )

    @model_validator(mode="after")
    def validate_target(self):

        target_required = {
            "required_chunk_present",
            "answer_contains",
            "answer_excludes",
        }

        if self.kind in target_required and not self.target:
            raise ValueError(
                f"{self.kind} requires a target."
            )

        return self


class RegressionTestCase(StrictModel):

    test_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    source_run_id: str

    title: str = Field(
        min_length=1,
        max_length=500,
    )

    input: DiagnosticRequest

    expected_failure_category: FindingCategory | None = None

    assertions: list[RegressionAssertion] = Field(
        min_length=1,
        max_length=30,
    )


class AssertionResult(StrictModel):

    assertion: RegressionAssertion

    passed: bool

    observed_value: str | None = None

    notes: str | None = None


class RegressionTestResult(StrictModel):

    test_id: str

    status: Literal[
        "passed",
        "failed",
        "error",
        "skipped",
    ]

    assertion_results: list[AssertionResult] = Field(
        default_factory=list
    )

    duration_ms: float = Field(
        default=0.0,
        ge=0.0,
    )

    executed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ============================================================
# 8. EXECUTION METADATA
# ============================================================

class AgentExecutionRecord(StrictModel):

    agent: AgentName

    status: Literal[
        "queued",
        "running",
        "completed",
        "failed",
        "skipped",
    ]

    attempt: int = Field(
        default=1,
        ge=1,
    )

    started_at: datetime | None = None

    finished_at: datetime | None = None

    duration_ms: float | None = Field(
        default=None,
        ge=0.0,
    )

    output_finding_ids: list[str] = Field(
        default_factory=list
    )


class ExecutionEvent(StrictModel):

    event_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    node_name: str

    agent: AgentName | None = None

    event_type: Literal[
        "started",
        "completed",
        "failed",
        "retrying",
        "skipped",
    ]

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    duration_ms: float | None = Field(
        default=None,
        ge=0.0,
    )

    detail: str | None = Field(
        default=None,
        max_length=2_000,
    )


# ============================================================
# 9. ERROR HANDLING
# ============================================================

class AgentError(StrictModel):

    error_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    node_name: str

    agent: AgentName | None = None

    error_code: str

    message: str = Field(
        min_length=1,
        max_length=2_000,
    )

    retryable: bool = False

    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    correlation_id: str


# ============================================================
# 10. RUN METADATA AND FINAL REPORT
# ============================================================

class RunMetadata(StrictModel):

    run_id: str

    status: Literal[
        "pending",
        "running",
        "completed",
        "partial",
        "failed",
    ] = "pending"

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    finished_at: datetime | None = None

    duration_ms: float | None = Field(
        default=None,
        ge=0.0,
    )

    app_version: str = "0.1.0"

    model_name: str | None = None

    model_provider: str | None = "ollama"


class DiagnosticReport(StrictModel):

    run_id: str

    status: Literal[
        "completed",
        "partial",
        "failed",
    ]

    summary: str

    primary_hypothesis: RootCauseHypothesis | None = None

    findings: list[AgentFinding] = Field(
        default_factory=list
    )

    recommendations: list[str] = Field(
        default_factory=list
    )

    regression_test_ids: list[str] = Field(
        default_factory=list
    )

    limitations: list[str] = Field(
        default_factory=list
    )