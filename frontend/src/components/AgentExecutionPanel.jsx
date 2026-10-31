import './AgentExecutionPanel.css'

const agentLabels = {
    retrieval_auditor: 'Retrieval Auditor',
    context_auditor: 'Context Auditor',
    grounding_auditor: 'Grounding Auditor',
    generation_auditor: 'Generation Auditor',
}

function formatDuration(duration) {
    if (duration === null || duration === undefined) {
        return 'Not available'
    }

    return `${duration.toFixed(2)} ms`
}

function AgentExecutionPanel({ executions = [] }) {
    return (
        <section className="agent-execution-panel">
            <div className="section-heading">
                <div>
                    <span className="eyebrow">AGENT OBSERVABILITY</span>
                    <h2>Agent execution monitor</h2>
                    <p>
                        Execution records returned by the LangGraph workflow.
                    </p>
                </div>

                <span className="section-tag">
                    {executions.length} AGENTS
                </span>
            </div>

            {executions.length === 0 ? (
                <div className="agent-empty-state">
                    No agent execution records available.
                </div>
            ) : (
                <div className="agent-execution-list">
                    {executions.map((execution) => (
                        <article
                            className="agent-execution-card"
                            key={`${execution.agent}-${execution.attempt}`}
                        >
                            <div className="agent-execution-icon">
                                ◈
                            </div>

                            <div className="agent-execution-info">
                                <h3>
                                    {agentLabels[execution.agent] ||
                                        execution.agent}
                                </h3>

                                <div className="agent-execution-metadata">
                                    <span>
                                        Attempt {execution.attempt}
                                    </span>

                                    <span>
                                        Duration: {formatDuration(
                                            execution.duration_ms,
                                        )}
                                    </span>
                                </div>

                                {execution.output_finding_ids?.length > 0 && (
                                    <span className="agent-findings-count">
                                        {execution.output_finding_ids.length}
                                        {' '}finding(s) produced
                                    </span>
                                )}
                            </div>

                            <span
                                className={`agent-status ${execution.status}`}
                            >
                                {execution.status}
                            </span>
                        </article>
                    ))}
                </div>
            )}
        </section>
    )
}

export default AgentExecutionPanel