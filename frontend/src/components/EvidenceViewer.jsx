import './EvidenceViewer.css'

const agentLabels = {
    retrieval_auditor: 'Retrieval Auditor',
    context_auditor: 'Context Auditor',
    grounding_auditor: 'Grounding Auditor',
    generation_auditor: 'Generation Auditor',
    root_cause_coordinator: 'Root Cause Coordinator',
    regression_test_generator: 'Regression Test Generator',
    verification_agent: 'Verification Agent',
}

const sourceLabels = {
    query: 'User query',
    retrieved_chunk: 'Retrieved document chunk',
    assembled_context: 'Assembled context',
    generated_answer: 'Generated answer',
    expected_answer: 'Expected answer',
}

const basisLabels = {
    direct_evidence: 'Direct evidence',
    inference: 'Inference',
}

function formatConfidence(value) {
    if (typeof value !== 'number' || !Number.isFinite(value)) {
        return 'Not available'
    }

    return value.toFixed(2)
}

function EvidenceCard({ finding }) {
    const evidence = finding.evidence ?? []
    const recommendations = finding.recommendations ?? []

    return (
        <article className="evidence-card">
            <div className="evidence-card-header">
                <div>
                    <span className="evidence-agent">
                        {agentLabels[finding.agent] || finding.agent}
                    </span>

                    <h3>{finding.category.replaceAll('_', ' ')}</h3>
                </div>

                <span className={`severity-pill ${finding.severity}`}>
                    {finding.severity}
                </span>
            </div>

            <p className="evidence-summary">
                {finding.summary}
            </p>

            {finding.details && (
                <div className="evidence-details">
                    <h4>Diagnostic details</h4>
                    <p>{finding.details}</p>
                </div>
            )}

            <div className="evidence-metadata">
                <div className="evidence-metadata-item">
                    <span>Evidence basis</span>
                    <strong>
                        {basisLabels[finding.evidence_basis] ||
                            finding.evidence_basis}
                    </strong>
                </div>

                <div className="evidence-metadata-item">
                    <span>Agent-reported confidence</span>
                    <strong>{formatConfidence(finding.confidence)}</strong>
                </div>
            </div>

            <div className="evidence-references">
                <h4>Supporting evidence ({evidence.length})</h4>

                {evidence.length === 0 ? (
                    <div className="no-evidence">
                        No evidence references were returned for this finding.
                        Review the source data before treating this finding as
                        independently verified.
                    </div>
                ) : (
                    evidence.map((reference, index) => (
                        <article
                            className="evidence-reference"
                            key={`${reference.source_type}-${reference.source_id}-${index}`}
                        >
                            <div className="evidence-reference-header">
                                <strong>
                                    {sourceLabels[reference.source_type] ||
                                        reference.source_type}
                                </strong>

                                <span>{reference.source_id}</span>
                            </div>

                            {reference.excerpt && (
                                <blockquote>
                                    {reference.excerpt}
                                </blockquote>
                            )}

                            {reference.rationale && (
                                <p className="evidence-rationale">
                                    <strong>Rationale:</strong>{' '}
                                    {reference.rationale}
                                </p>
                            )}
                        </article>
                    ))
                )}
            </div>

            {recommendations.length > 0 && (
                <div className="evidence-recommendations">
                    <h4>Agent recommendations</h4>

                    <ul>
                        {recommendations.map((recommendation, index) => (
                            <li key={index}>{recommendation}</li>
                        ))}
                    </ul>
                </div>
            )}
        </article>
    )
}

function EvidenceViewer({ findings = [] }) {
    return (
        <section className="evidence-viewer">
            <div className="section-heading">
                <div>
                    <span className="eyebrow">DIAGNOSTIC EVIDENCE</span>
                    <h2>Evidence and finding analysis</h2>
                    <p>
                        Inspect the evidence, reasoning basis and recommendations
                        returned by each specialist.
                    </p>
                </div>

                <span className="section-tag">
                    {findings.length} FINDINGS
                </span>
            </div>

            {findings.length === 0 ? (
                <div className="evidence-empty">
                    No diagnostic findings were returned for this run.
                </div>
            ) : (
                <div className="evidence-list">
                    {findings.map((finding, index) => (
                        <EvidenceCard
                            key={finding.finding_id || index}
                            finding={finding}
                        />
                    ))}
                </div>
            )}

            <p className="confidence-disclaimer">
                Confidence values represent scores reported by the deterministic
                diagnostic agents. They should not be interpreted as calibrated
                probabilities of diagnostic correctness.
            </p>
        </section>
    )
}

export default EvidenceViewer