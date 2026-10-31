import './RunHistoryPanel.css'

function formatTimestamp(value) {
    if (!value) {
        return 'Timestamp unavailable'
    }

    const date = new Date(value)

    if (Number.isNaN(date.getTime())) {
        return 'Invalid timestamp'
    }

    return new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
    }).format(date)
}

function RunHistoryPanel({
    history = [],
    selectedRunId,
    onSelect,
}) {
    return (
        <section className="run-history-panel">
            <div className="section-heading">
                <div>
                    <span className="eyebrow">SESSION ACTIVITY</span>
                    <h2>Diagnostic run history</h2>
                    <p>
                        Review previous diagnostic executions from this page session.
                    </p>
                </div>

                <span className="section-tag">
                    {history.length} RUNS
                </span>
            </div>

            {history.length === 0 ? (
                <div className="history-empty">
                    <strong>No diagnostic history yet</strong>
                    <p>
                        Your completed diagnostic runs will appear here.
                    </p>
                </div>
            ) : (
                <div className="history-list">
                    {history.map((entry, index) => {
                        const report = entry.response.report
                        const metadata = entry.response.run_metadata
                        const findings = report.findings ?? []

                        const isSelected =
                            metadata.run_id === selectedRunId

                        return (
                            <button
                                type="button"
                                className={`history-entry ${isSelected ? 'selected' : ''
                                    }`}
                                key={metadata.run_id}
                                onClick={() => onSelect(entry)}
                                aria-pressed={isSelected}
                            >
                                <div className="history-entry-main">
                                    <div className="history-entry-heading">
                                        <strong>Run #{history.length - index}</strong>

                                        <span
                                            className={`history-status ${metadata.status}`}
                                        >
                                            {metadata.status}
                                        </span>
                                    </div>

                                    <span className="history-run-id">
                                        ID: {metadata.run_id}
                                    </span>

                                    <span className="history-summary">
                                        {findings.length > 0
                                            ? findings.map((finding) =>
                                                finding.category,
                                            ).join(', ')
                                            : 'No findings returned'}
                                    </span>

                                    <span className="history-timestamp">
                                        {formatTimestamp(metadata.created_at)}
                                    </span>
                                </div>

                                <div className="history-entry-count">
                                    <strong>{findings.length}</strong>
                                    <span>Findings</span>
                                </div>
                            </button>
                        )
                    })}
                </div>
            )}

            <p className="history-disclaimer">
                Session-only history. Reloading this page clears the run history.
            </p>
        </section>
    )
}

export default RunHistoryPanel