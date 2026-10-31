import RunHistoryPanel from './components/RunHistoryPanel'
import RunMetadataPanel from './components/RunMetadataPanel'
import EvidenceViewer from './components/EvidenceViewer'
import ExecutionTimeline from './components/ExecutionTimeline'
import AgentExecutionPanel from './components/AgentExecutionPanel'
import { useEffect, useState } from 'react'
import { checkBackendHealth, runDiagnostic } from './services/api'
import DiagnosticForm from './components/DiagnosticForm'
import './App.css'

const navigation = [
  { label: 'Overview', icon: '◫', href: '#overview', active: true },
  { label: 'Diagnostics', icon: '⌕', href: '#diagnostics' },
  { label: 'Agent Monitor', icon: '◈', href: '#agents' },
]

function Sidebar({ apiStatus }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-icon">R</div>
        <div>
          <h2>RAG Doctor</h2>
          <span>DIAGNOSTIC PLATFORM</span>
        </div>
      </div>

      <div className="sidebar-label">WORKSPACE</div>

      <nav className="sidebar-nav">
        {navigation.map((item) => (
          <a
            key={item.label}
            href={item.href}
            className={`nav-item ${item.active ? 'active' : ''}`}
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
          </a>
        ))}
      </nav>

      <div className="sidebar-bottom">
        <div className="sidebar-status">
          <span className={`status-dot ${apiStatus}`} />
          <div>
            <strong>
              {apiStatus === 'connected'
                ? 'Backend connected'
                : apiStatus === 'checking'
                  ? 'Checking backend...'
                  : 'Backend offline'}
            </strong>

            <span>FastAPI connection</span>
          </div>
        </div>

        <div className="sidebar-version">
          RAG Doctor · MVP 0.1
        </div>
      </div>
    </aside>
  )
}

function Header() {
  return (
    <header className="topbar">
      <div className="breadcrumb">
        <span>Workspace</span>
        <span className="breadcrumb-separator">/</span>
        <strong>Overview</strong>
      </div>

      <div className="topbar-right">
        <span className="environment-badge">
          <span className="status-dot neutral" />
          LOCAL DEVELOPMENT
        </span>

        <div className="user-avatar">RD</div>
      </div>
    </header>
  )
}

function OverviewCard({ label, value, description, icon }) {
  return (
    <article className="overview-card">
      <div className="card-top">
        <span className="card-label">{label}</span>
        <span className="card-icon">{icon}</span>
      </div>

      <h3>{value}</h3>
      <p>{description}</p>
    </article>
  )
}

function App() {
  const [apiStatus, setApiStatus] = useState('checking')
  const [isLoading, setIsLoading] = useState(false)
  const [diagnosticResult, setDiagnosticResult] = useState(null)
  const [diagnosticError, setDiagnosticError] = useState('')
  const [runCount, setRunCount] = useState(0)
  const [runHistory, setRunHistory] = useState([])
  const [selectedRunId, setSelectedRunId] = useState(null)

  // Check backend connectivity when the dashboard loads.
  useEffect(() => {
    let active = true

    checkBackendHealth()
      .then(() => {
        if (active) {
          setApiStatus('connected')
        }
      })
      .catch(() => {
        if (active) {
          setApiStatus('offline')
        }
      })

    return () => {
      active = false
    }
  }, [])

  // Submit diagnostic input to the existing FastAPI backend.
  async function handleDiagnosticSubmit(payload) {
    setIsLoading(true)
    setDiagnosticError('')
    setDiagnosticResult(null)
    setSelectedRunId(null)

    try {
      const result = await runDiagnostic(payload)

      setDiagnosticResult(result)
      setRunCount((current) => current + 1)
      setApiStatus('connected')

      const historyEntry = {
        response: result,
      }

      setRunHistory((current) =>
        [
          historyEntry,
          ...current.filter(
            (entry) =>
              entry.response.run_metadata.run_id !==
              result.run_metadata.run_id,
          ),
        ].slice(0, 20),
      )

      setSelectedRunId(result.run_metadata.run_id)
    } catch (error) {
      setDiagnosticError(error.message)
      setApiStatus(
        error.status ? 'connected' : 'offline',
      )
    } finally {
      setIsLoading(false)
    }
  }
  function handleHistorySelect(entry) {
    setDiagnosticResult(entry.response)
    setDiagnosticError('')
    setSelectedRunId(
      entry.response.run_metadata.run_id,
    )
  }

  const report = diagnosticResult?.report
  const findings = report?.findings ?? []
  const executions = diagnosticResult?.agent_executions ?? []
  const executionEvents = diagnosticResult?.execution_events ?? []
  const errors = diagnosticResult?.errors ?? []

  const completedAgents = executions.filter(
    (execution) => execution.status === 'completed',
  ).length

  return (
    <div className="app-shell">
      <Sidebar apiStatus={apiStatus} />

      <div className="main-area">
        <Header />

        <main className="dashboard-content" id="overview">
          <section className="page-heading">
            <div>
              <span className="eyebrow">
                RAG SYSTEM OBSERVABILITY
              </span>

              <h1>Diagnostic Overview</h1>

              <p>
                Inspect, evaluate and troubleshoot your
                retrieval-augmented generation pipelines.
              </p>
            </div>

            <div className="workspace-badge">
              <span className={`status-dot ${apiStatus}`} />
              {apiStatus === 'connected'
                ? 'Backend connected'
                : apiStatus === 'checking'
                  ? 'Checking connection'
                  : 'Backend unavailable'}
            </div>
          </section>

          <section className="overview-grid">
            <OverviewCard
              label="DIAGNOSTIC RUNS"
              value={String(runCount)}
              description={
                runCount === 0
                  ? 'No successful runs in this session'
                  : 'Successful diagnostic executions'
              }
              icon="◷"
            />

            <OverviewCard
              label="SPECIALIST AGENTS"
              value="04"
              description="Deterministic agents configured"
              icon="◈"
            />

            <OverviewCard
              label="API INTEGRATION"
              value={
                apiStatus === 'connected'
                  ? 'Connected'
                  : apiStatus === 'checking'
                    ? 'Checking...'
                    : 'Offline'
              }
              description="FastAPI backend health"
              icon="⌘"
            />
          </section>

          {runHistory.length > 0 && (
            <RunHistoryPanel
              history={runHistory}
              selectedRunId={selectedRunId}
              onSelect={handleHistorySelect}
            />
          )}

          <section className="workspace-section" id="diagnostics">
            <DiagnosticForm
              onSubmit={handleDiagnosticSubmit}
              isLoading={isLoading}
            />

            {diagnosticError && (
              <div className="diagnostic-feedback error" role="alert">
                <strong>Diagnostic failed</strong>
                <p>{diagnosticError}</p>
              </div>
            )}

            {report && (
              <section
                className="diagnostic-result-preview"
                aria-live="polite"
              >
                <div className="result-heading">
                  <div>
                    <span className="eyebrow">
                      DIAGNOSTIC RESPONSE
                    </span>

                    <h2>Diagnostic report</h2>
                    <p>{report.summary}</p>
                  </div>

                  <span
                    className={`result-status ${report.status}`}
                  >
                    {report.status}
                  </span>
                </div>

                <div className="result-metrics">
                  <div>
                    <span>Findings</span>
                    <strong>{findings.length}</strong>
                  </div>

                  <div>
                    <span>Agents completed</span>
                    <strong>
                      {completedAgents}/{executions.length}
                    </strong>
                  </div>

                  <div>
                    <span>Execution events</span>
                    <strong>{executionEvents.length}</strong>
                  </div>

                  <div>
                    <span>Errors</span>
                    <strong>{errors.length}</strong>
                  </div>
                </div>

                <RunMetadataPanel
                  metadata={diagnosticResult.run_metadata}
                  limitations={report.limitations ?? []}
                />

                <EvidenceViewer findings={findings} />


                {report.primary_hypothesis && (
                  <div className="result-hypothesis">
                    <h3>Primary root-cause hypothesis</h3>
                    <p>
                      {report.primary_hypothesis.explanation}
                    </p>
                  </div>
                )}

                {report.recommendations?.length > 0 && (
                  <div className="result-recommendations">
                    <h3>Recommendations</h3>

                    <ul>
                      {report.recommendations.map(
                        (recommendation, index) => (
                          <li key={index}>{recommendation}</li>
                        ),
                      )}
                    </ul>
                  </div>
                )}
              </section>
            )}
          </section>

          {diagnosticResult && (
            <AgentExecutionPanel executions={executions} />
          )}

          {diagnosticResult && (
            <ExecutionTimeline events={executionEvents} />
          )}
          <section className="agent-section" id="agents">
            <div className="section-heading">
              <div>
                <span className="eyebrow">EXECUTION ENGINE</span>
                <h2>Specialist agent architecture</h2>
              </div>

              <span className="section-tag">LANGGRAPH</span>
            </div>

            <div className="agent-overview">
              <div className="agent-indicator">◈</div>

              <div>
                <h3>Four specialist agents</h3>
                <p>
                  Independent deterministic checks coordinated
                  through the existing LangGraph workflow.
                </p>
              </div>

              <span className="configured-label">
                CONFIGURED
              </span>
            </div>
          </section>
        </main>
      </div>
    </div>
  )
}

export default App