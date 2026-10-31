import './ExecutionTimeline.css'

const agentLabels = {
    retrieval_auditor: 'Retrieval Auditor',
    context_auditor: 'Context Auditor',
    grounding_auditor: 'Grounding Auditor',
    generation_auditor: 'Generation Auditor',
    root_cause_coordinator: 'Root Cause Coordinator',
    regression_test_generator: 'Regression Test Generator',
    verification_agent: 'Verification Agent',
}

const eventLabels = {
    started: 'Started',
    completed: 'Completed',
    failed: 'Failed',
    retrying: 'Retrying',
    skipped: 'Skipped',
}

function formatTimestamp(value) {
    if (!value) {
        return 'Timestamp unavailable'
    }

    const date = new Date(value)

    if (Number.isNaN(date.getTime())) {
        return String(value)
    }

    return new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'medium',
    }).format(date)
}

function formatDuration(value) {
    if (value === null || value === undefined) {
        return null
    }

    return `${Number(value).toFixed(2)} ms`
}

function ExecutionTimeline({ events = [] }) {
    const sortedEvents = [...events].sort(
        (first, second) =>
            new Date(first.timestamp).getTime() -
            new Date(second.timestamp).getTime(),
    )

    return (
        <section className="execution-timeline">
            <div className="section-heading">
                <div>
                    <span className="eyebrow">WORKFLOW TRACE</span>
                    <h2>Execution timeline</h2>
                    <p>
                        Recorded workflow events returned by LangGraph.
                    </p>
                </div>

                <span className="section-tag">
                    {events.length} EVENTS
                </span>
            </div>

            {sortedEvents.length === 0 ? (
                <div className="timeline-empty">
                    No execution events are available for this run.
                </div>
            ) : (
                <div className="timeline-list">
                    {sortedEvents.map((event, index) => {
                        const eventType = event.event_type

                        const agentName = event.agent
                            ? agentLabels[event.agent] || event.agent
                            : event.node_name

                        return (
                            <article
                                className="timeline-item"
                                key={event.event_id}
                            >
                                <div className="timeline-track">
                                    <span
                                        className={`timeline-marker ${eventType}`}
                                    />
                                    {index !== sortedEvents.length - 1 && (
                                        <span className="timeline-connector" />
                                    )}
                                </div>

                                <div className="timeline-content">
                                    <div className="timeline-item-heading">
                                        <div>
                                            <strong>{agentName}</strong>

                                            <span className="timeline-node">
                                                Node: {event.node_name}
                                            </span>
                                        </div>

                                        <span
                                            className={`timeline-event-badge ${eventType}`}
                                        >
                                            {eventLabels[eventType] || eventType}
                                        </span>
                                    </div>

                                    <div className="timeline-metadata">
                                        <span>
                                            {formatTimestamp(event.timestamp)}
                                        </span>

                                        {formatDuration(event.duration_ms) && (
                                            <span>
                                                Duration: {formatDuration(event.duration_ms)}
                                            </span>
                                        )}
                                    </div>

                                    {event.detail && (
                                        <p className="timeline-detail">
                                            {event.detail}
                                        </p>
                                    )}
                                </div>
                            </article>
                        )
                    })}
                </div>
            )}
        </section>
    )
}

export default ExecutionTimeline