import './RunMetadataPanel.css'

function formatTimestamp(value) {
    if (!value) {
        return 'Not available'
    }

    const date = new Date(value)

    if (Number.isNaN(date.getTime())) {
        return 'Invalid timestamp'
    }

    return new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'medium',
    }).format(date)
}

function formatDuration(value) {
    if (typeof value !== 'number' || !Number.isFinite(value)) {
        return 'Not available'
    }

    return `${value.toFixed(2)} ms`
}

function MetadataItem({ label, value, fullWidth = false }) {
    return (
        <div
            className={`metadata-item ${fullWidth ? 'full-width' : ''}`}
        >
            <span>{label}</span>
            <strong>{value ?? 'Not available'}</strong>
        </div>
    )
}

function RunMetadataPanel({ metadata, limitations = [] }) {
    if (!metadata) {
        return (
            <section className="run-metadata-panel">
                <div className="metadata-unavailable">
                    Run metadata was not included in the API response.
                </div>
            </section>
        )
    }

    return (
        <section className="run-metadata-panel">
            <div className="section-heading">
                <div>
                    <span className="eyebrow">EXECUTION METADATA</span>
                    <h2>Diagnostic run information</h2>
                    <p>
                        Traceability and execution details returned by FastAPI.
                    </p>
                </div>

                <span className="section-tag">
                    {metadata.status?.toUpperCase() || 'UNKNOWN'}
                </span>
            </div>

            <div className="metadata-grid">
                <MetadataItem
                    label="Run ID"
                    value={metadata.run_id}
                    fullWidth
                />

                <MetadataItem
                    label="Execution status"
                    value={metadata.status}
                />

                <MetadataItem
                    label="Execution duration"
                    value={formatDuration(metadata.duration_ms)}
                />

                <MetadataItem
                    label="Created at"
                    value={formatTimestamp(metadata.created_at)}
                />

                <MetadataItem
                    label="Finished at"
                    value={formatTimestamp(metadata.finished_at)}
                />

                <MetadataItem
                    label="Application version"
                    value={metadata.app_version}
                />

                <MetadataItem
                    label="Model name"
                    value={metadata.model_name}
                />

                <MetadataItem
                    label="Model provider"
                    value={metadata.model_provider}
                />
            </div>

            <div className="limitations-section">
                <h3>Diagnostic limitations</h3>

                {limitations.length === 0 ? (
                    <p className="no-limitations">
                        No limitations were returned by the backend for this run.
                    </p>
                ) : (
                    <ul>
                        {limitations.map((limitation, index) => (
                            <li key={`${index}-${limitation}`}>
                                {limitation}
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </section>
    )
}

export default RunMetadataPanel