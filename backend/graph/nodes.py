
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from time import perf_counter
from typing import Callable

from backend.api.schemas import (
    AgentError,
    AgentExecutionRecord,
    AgentFinding,
    AgentName,
    DiagnosticRequest,
    ExecutionEvent,
    EvidenceReference,
    FindingCategory,
    FindingSeverity,
)

from backend.graph.state import RAGDoctorState


# ============================================================
# CONFIGURATION
# ============================================================

# Initial heuristic only. Assumes relevance scores are normalized
# to [0, 1] and higher scores indicate greater relevance.
LOW_RELEVANCE_THRESHOLD = 0.25

# Lexical overlap is a screening heuristic, not an entailment test.
MIN_ANSWER_TOKENS = 8
MAX_UNSUPPORTED_TOKEN_RATIO = 0.80

MAX_EVIDENCE_REFERENCES = 20

Analyzer = Callable[
    [DiagnosticRequest],
    list[AgentFinding],
]


# ============================================================
# COMMON HELPERS
# ============================================================

def normalize_text(text: str) -> str:
    """Normalize text for deterministic comparisons."""
    return " ".join(text.casefold().split())


def tokenize(text: str) -> set[str]:
    """
    Extract simple lexical tokens.

    This is intentionally deterministic. It does not perform
    stemming, synonym matching, or semantic similarity.
    """
    return set(
        re.findall(r"[a-zA-Z0-9_]{3,}", text.casefold())
    )


def effective_context(
    request: DiagnosticRequest,
) -> tuple[str, bool]:
    """
    Return the supplied assembled context when available.

    Otherwise, construct a temporary context by joining retrieved
    chunks in rank order where ranks exist.

    Returns:
        (context_text, was_assembled_from_chunks)

    The generated context is local to the diagnostic execution;
    it is not persisted into the shared state.
    """
    if request.assembled_context is not None:
        return request.assembled_context, False

    chunks = sorted(
        request.retrieved_chunks,
        key=lambda chunk: (
            chunk.rank is None,
            chunk.rank or 0,
        ),
    )

    context = "\n\n".join(
        chunk.content for chunk in chunks
    )

    return context, True


# ============================================================
# COMMON EXECUTION WRAPPER
# ============================================================

def execute_specialist(
    state: RAGDoctorState,
    agent: AgentName,
    analyzer: Analyzer,
) -> dict[str, object]:
    """
    Execute one specialist diagnostic node.

    Returns partial LangGraph state updates. Collection fields
    use the reducers declared in RAGDoctorState.

    Exceptions are converted into structured errors so that
    one failed specialist does not automatically stop the
    other parallel diagnostic nodes.
    """
    request = state["request"]

    started_at = datetime.now(timezone.utc)
    start_clock = perf_counter()

    findings: list[AgentFinding] = []
    errors: list[AgentError] = []

    status = "completed"

    try:
        findings = analyzer(request)

    except Exception as exc:
        status = "failed"

        # Avoid placing potentially sensitive exception contents
        # into the externally visible diagnostic report.
        error_type = type(exc).__name__

        errors.append(
            AgentError(
                node_name=agent.value,
                agent=agent,
                error_code=error_type,
                message=(
                    f"{agent.value} failed with "
                    f"{error_type}."
                ),
                retryable=False,
                correlation_id=request.run_id,
            )
        )

    finished_at = datetime.now(timezone.utc)

    duration_ms = (
        perf_counter() - start_clock
    ) * 1000

    execution_record = AgentExecutionRecord(
        agent=agent,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        output_finding_ids=[
            finding.finding_id for finding in findings
        ],
    )

    events = [
        ExecutionEvent(
            node_name=agent.value,
            agent=agent,
            event_type="started",
            timestamp=started_at,
        ),
        ExecutionEvent(
            node_name=agent.value,
            agent=agent,
            event_type=(
                "completed" if status == "completed"
                else "failed"
            ),
            timestamp=finished_at,
            duration_ms=duration_ms,
            detail=(
                f"Produced {len(findings)} findings."
                if status == "completed"
                else f"Failed with {len(errors)} error(s)."
            ),
        ),
    ]

    return {
        "findings": findings,
        "agent_executions": [execution_record],
        "execution_events": events,
        "errors": errors,
    }


# ============================================================
# AGENT 1 — RETRIEVAL AUDITOR
# ============================================================

def analyze_retrieval(
    request: DiagnosticRequest,
) -> list[AgentFinding]:
    """
    Audit retrieved documents for missing results and
    suspiciously low normalized relevance scores.
    """
    findings: list[AgentFinding] = []

    chunks = request.retrieved_chunks

    # Case 1: No documents retrieved.
    if not chunks:
        findings.append(
            AgentFinding(
                agent=AgentName.RETRIEVAL_AUDITOR,
                category=FindingCategory.RETRIEVAL_MISS,
                severity=FindingSeverity.CRITICAL,
                summary="No documents were retrieved.",
                details=(
                    "The execution trace contains no retrieved "
                    "document chunks for the submitted query."
                ),
                confidence=0.99,
                evidence_basis="direct_evidence",
                evidence=[
                    EvidenceReference(
                        source_type="query",
                        source_id="retrieved_chunks",
                        excerpt=request.query[:500],
                        rationale=(
                            "The supplied retrieval result "
                            "collection is empty."
                        ),
                    )
                ],
                recommendations=[
                    "Inspect document ingestion and indexing.",
                    "Verify query embedding generation.",
                    "Check vector search filters and retrieval settings.",
                    "Confirm that the relevant documents exist."
                ],
            )
        )
        return findings

    # Case 2: Available scores indicate low relevance.
    scored_chunks = [
        chunk for chunk in chunks
        if chunk.score is not None
    ]

    if (
        scored_chunks
        and max(chunk.score for chunk in scored_chunks)
        < LOW_RELEVANCE_THRESHOLD
    ):
        findings.append(
            AgentFinding(
                agent=AgentName.RETRIEVAL_AUDITOR,
                category=FindingCategory.LOW_RELEVANCE,
                severity=FindingSeverity.HIGH,
                summary="Retrieved chunks have low relevance scores.",
                details=(
                    "Every available normalized relevance score "
                    f"is below {LOW_RELEVANCE_THRESHOLD}. "
                    "This may indicate a retrieval or ranking issue."
                ),
                confidence=0.55,
                evidence_basis="direct_evidence",
                evidence=[
                    EvidenceReference(
                        source_type="retrieved_chunk",
                        source_id=chunk.chunk_id,
                        excerpt=chunk.content[:500],
                        rationale=(
                            f"Observed normalized score: "
                            f"{chunk.score}"
                        ),
                    )
                    for chunk in scored_chunks[
                        :MAX_EVIDENCE_REFERENCES
                    ]
                ],
                recommendations=[
                    "Inspect embedding model compatibility.",
                    "Evaluate query-document similarity.",
                    "Review retrieval top-k and reranking.",
                    "Compare results against labelled relevant documents."
                ],
            )
        )

    return findings


def retrieval_auditor(
    state: RAGDoctorState,
) -> dict[str, object]:
    """LangGraph node: inspect retrieval quality."""
    return execute_specialist(
        state,
        AgentName.RETRIEVAL_AUDITOR,
        analyze_retrieval,
    )


# ============================================================
# AGENT 2 — CONTEXT AUDITOR
# ============================================================

def analyze_context(
    request: DiagnosticRequest,
) -> list[AgentFinding]:
    """
    Assemble fallback context when necessary and inspect it
    for empty content, omitted chunks and duplicate chunks.
    """
    findings: list[AgentFinding] = []

    chunks = request.retrieved_chunks

    context, assembled_from_chunks = effective_context(
        request
    )

    # Case 1: Retrieved chunks exist, but supplied context is empty.
    if chunks and request.assembled_context is not None:
        if not request.assembled_context.strip():
            findings.append(
                AgentFinding(
                    agent=AgentName.CONTEXT_AUDITOR,
                    category=FindingCategory.CONTEXT_TRUNCATION,
                    severity=FindingSeverity.CRITICAL,
                    summary="Assembled context is empty.",
                    details=(
                        "Retrieved chunks are available, but the "
                        "explicitly supplied assembled context "
                        "contains no text."
                    ),
                    confidence=0.99,
                    evidence_basis="direct_evidence",
                    evidence=[
                        EvidenceReference(
                            source_type="assembled_context",
                            source_id="assembled_context",
                            rationale=(
                                "Explicit assembled context is empty."
                            ),
                        )
                    ],
                    recommendations=[
                        "Inspect context construction.",
                        "Check token-budget and truncation logic.",
                        "Verify prompt assembly and chunk formatting."
                    ],
                )
            )
            return findings

    # Case 2: Chunks were omitted from an explicitly supplied context.
    if chunks and request.assembled_context:
        normalized_context = normalize_text(context)

        omitted_chunks = [
            chunk for chunk in chunks
            if normalize_text(chunk.content)
            and normalize_text(chunk.content)
            not in normalized_context
        ]

        if omitted_chunks:
            findings.append(
                AgentFinding(
                    agent=AgentName.CONTEXT_AUDITOR,
                    category=FindingCategory.CONTEXT_TRUNCATION,
                    severity=FindingSeverity.MEDIUM,
                    summary="Retrieved chunks may be missing from context.",
                    details=(
                        f"{len(omitted_chunks)} retrieved chunk(s) "
                        "were not found as complete normalized text "
                        "inside the assembled context. This may "
                        "indicate filtering or truncation."
                    ),
                    confidence=0.65,
                    evidence_basis="direct_evidence",
                    evidence=[
                        EvidenceReference(
                            source_type="retrieved_chunk",
                            source_id=chunk.chunk_id,
                            excerpt=chunk.content[:500],
                            rationale=(
                                "Complete normalized chunk text "
                                "was not found in assembled context."
                            ),
                        )
                        for chunk in omitted_chunks[
                            :MAX_EVIDENCE_REFERENCES
                        ]
                    ],
                    recommendations=[
                        "Inspect context selection and filtering.",
                        "Review token-window truncation.",
                        "Verify that relevant chunks reach the prompt."
                    ],
                )
            )

    # Case 3: Exact duplicate chunks.
    duplicate_groups: dict[str, list] = defaultdict(list)

    for chunk in chunks:
        normalized = normalize_text(chunk.content)

        if normalized:
            duplicate_groups[normalized].append(chunk)

    duplicates = [
        group
        for group in duplicate_groups.values()
        if len(group) > 1
    ]

    if duplicates:
        duplicate_chunks = [
            chunk
            for group in duplicates
            for chunk in group
        ]

        findings.append(
            AgentFinding(
                agent=AgentName.CONTEXT_AUDITOR,
                category=FindingCategory.DUPLICATE_CONTEXT,
                severity=FindingSeverity.MEDIUM,
                summary="Duplicate retrieved chunks detected.",
                details=(
                    f"Detected {len(duplicates)} groups of "
                    "identical normalized chunk content."
                ),
                confidence=0.99,
                evidence_basis="direct_evidence",
                evidence=[
                    EvidenceReference(
                        source_type="retrieved_chunk",
                        source_id=chunk.chunk_id,
                        excerpt=chunk.content[:500],
                        rationale="Identical normalized chunk content.",
                    )
                    for chunk in duplicate_chunks[
                        :MAX_EVIDENCE_REFERENCES
                    ]
                ],
                recommendations=[
                    "Introduce duplicate chunk filtering.",
                    "Review document chunking and overlap settings.",
                    "Inspect duplicate document ingestion."
                ],
            )
        )

    # The assembled fallback context is intentionally local.
    # It is inspected here but not written to shared state.

    return findings


def context_auditor(
    state: RAGDoctorState,
) -> dict[str, object]:
    """LangGraph node: assemble and audit context."""
    return execute_specialist(
        state,
        AgentName.CONTEXT_AUDITOR,
        analyze_context,
    )


# ============================================================
# AGENT 3 — GROUNDING AUDITOR
# ============================================================

STOPWORDS = {
    "the", "and", "for", "that", "this",
    "with", "from", "are", "was", "were",
    "has", "have", "had", "you", "your",
    "what", "when", "where", "which",
    "how", "why", "can", "will", "not",
    "but", "its", "into", "than", "then",
    "there", "their", "they", "them",
    "about", "also", "should", "would",
}


def analyze_grounding(
    request: DiagnosticRequest,
) -> list[AgentFinding]:
    """
    Identify potential lexical mismatches between the answer
    and the supplied evidence.

    This is a preliminary screening heuristic, not semantic
    entailment or proof of hallucination.
    """
    findings: list[AgentFinding] = []

    answer = request.generated_answer

    context, assembled_from_chunks = effective_context(
        request
    )

    if not answer.strip() or not context.strip():
        return findings

    answer_tokens = tokenize(answer) - STOPWORDS
    context_tokens = tokenize(context) - STOPWORDS

    if len(answer_tokens) < MIN_ANSWER_TOKENS:
        return findings

    unsupported_tokens = answer_tokens - context_tokens

    unsupported_ratio = (
        len(unsupported_tokens) / len(answer_tokens)
    )

    if unsupported_ratio >= MAX_UNSUPPORTED_TOKEN_RATIO:
        evidence = [
            EvidenceReference(
                source_type="generated_answer",
                source_id="generated_answer",
                excerpt=answer[:500],
                rationale=(
                    "Generated answer evaluated by lexical overlap."
                ),
            )
        ]

        if assembled_from_chunks:
            evidence.extend(
                EvidenceReference(
                    source_type="retrieved_chunk",
                    source_id=chunk.chunk_id,
                    excerpt=chunk.content[:300],
                    rationale="Retrieved evidence used for comparison.",
                )
                for chunk in request.retrieved_chunks[
                    :MAX_EVIDENCE_REFERENCES - 1
                ]
            )
        else:
            evidence.append(
                EvidenceReference(
                    source_type="assembled_context",
                    source_id="assembled_context",
                    excerpt=context[:500],
                    rationale="Supplied context used for comparison.",
                )
            )

        findings.append(
            AgentFinding(
                agent=AgentName.GROUNDING_AUDITOR,
                category=FindingCategory.UNSUPPORTED_CLAIM,
                severity=FindingSeverity.MEDIUM,
                summary="Potential answer-evidence vocabulary mismatch.",
                details=(
                    f"{unsupported_ratio:.0%} of distinct answer "
                    "tokens are absent from the evidence vocabulary. "
                    "Missing vocabulary does not prove that a claim "
                    "is false or unsupported semantically."
                ),
                confidence=0.35,
                evidence_basis="inference",
                evidence=evidence[:MAX_EVIDENCE_REFERENCES],
                recommendations=[
                    "Inspect factual claims individually.",
                    "Verify important claims against source passages.",
                    "Add semantic entailment evaluation.",
                    "Check citation-to-claim alignment."
                ],
            )
        )

    return findings


def grounding_auditor(
    state: RAGDoctorState,
) -> dict[str, object]:
    """LangGraph node: inspect answer grounding."""
    return execute_specialist(
        state,
        AgentName.GROUNDING_AUDITOR,
        analyze_grounding,
    )


# ============================================================
# AGENT 4 — GENERATION AUDITOR
# ============================================================

def analyze_generation(
    request: DiagnosticRequest,
) -> list[AgentFinding]:
    """
    Inspect the available generation output.

    The current request schema does not include finish reason,
    token usage or model response metadata. Therefore this
    initial auditor only reports failures observable from the
    supplied generated answer.
    """
    findings: list[AgentFinding] = []

    if not request.generated_answer.strip():
        findings.append(
            AgentFinding(
                agent=AgentName.GENERATION_AUDITOR,
                category=FindingCategory.GENERATION_ERROR,
                severity=FindingSeverity.HIGH,
                summary="The generated answer is empty.",
                details=(
                    "The supplied RAG execution trace contains "
                    "no generated answer."
                ),
                confidence=0.99,
                evidence_basis="direct_evidence",
                evidence=[
                    EvidenceReference(
                        source_type="generated_answer",
                        source_id="generated_answer",
                        rationale="Generated answer is empty or whitespace.",
                    )
                ],
                recommendations=[
                    "Inspect model availability and request timeouts.",
                    "Check prompt construction.",
                    "Review response parsing and output validation.",
                    "Inspect model execution logs."
                ],
            )
        )

    return findings


def generation_auditor(
    state: RAGDoctorState,
) -> dict[str, object]:
    """LangGraph node: inspect generation output."""
    return execute_specialist(
        state,
        AgentName.GENERATION_AUDITOR,
        analyze_generation,
    )
