import { useEffect, useMemo, useRef, useState } from 'react'
import { Activity, Database, FlaskConical, Loader2, Send, Server, Workflow } from 'lucide-react'
import { api, type ConversationDecision, type ConversationRouteContext, type ModelPlan, type PlannedStep, type ProviderView, type ReviewAgentRun, type TaskRecord, type TimelineEvent, type WorkflowView } from './api'

const defaultPrompt =
  'Plan bulk RNA-seq treatment vs control analysis with QC, counting, differential summary, and report.'

const promptExamples = [
  {
    title: 'Bulk RNA-seq',
    description: 'Executable toy workflow',
    workflowKey: 'bulk_rna_seq',
    prompt: defaultPrompt,
  },
  {
    title: 'Single-cell RNA-seq',
    description: 'Executable Scanpy workflow',
    workflowKey: 'single_cell_rna_seq',
    prompt: 'I have a 10x-style single-cell RNA-seq dataset and want to identify cell clusters, marker genes, and treatment-associated cell-state changes. Please plan the analysis using the available public tools.',
  },
  {
    title: 'Label-free proteomics',
    description: 'Executable limma workflow',
    workflowKey: 'proteomics_lfq',
    prompt: 'I have label-free proteomics spectra for treatment and control samples. Please plan quality control, peptide or protein identification, quantification, differential abundance analysis, and a concise interpretation.',
  },
]

type ChatMessage = {
  id: string
  role: 'assistant' | 'user'
  content: string
  decision?: ConversationDecision
}

function upsertTaskHistory(current: TaskRecord[], task: TaskRecord) {
  return [task, ...current.filter((item) => item.id !== task.id)]
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    .slice(0, 12)
}

function taskWorkflowName(task: TaskRecord) {
  return task.modelPlan?.workflowName || task.result?.modelPlan.workflowName || task.result?.workflowKey || 'Planning workflow'
}

function shortTaskId(task: TaskRecord) {
  return task.id.slice(0, 8)
}

function formatDirection(direction: string) {
  if (direction === 'up') return 'Up'
  if (direction === 'down') return 'Down'
  return 'Stable'
}

function previousConversationContext(messages: ChatMessage[]): Pick<ConversationRouteContext, 'previousAction' | 'previousWorkflowKey' | 'previousAnalysisPrompt' | 'previousMessage'> {
  let previousIndex = -1
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index].role === 'assistant' && messages[index].decision?.workflowKey) {
      previousIndex = index
      break
    }
  }
  const previous = previousIndex >= 0 ? messages[previousIndex] : undefined
  if (!previous?.decision) return {}
  let previousUser: ChatMessage | undefined
  for (let index = previousIndex - 1; index >= 0; index -= 1) {
    if (messages[index].role === 'user') {
      previousUser = messages[index]
      break
    }
  }
  return {
    previousAction: previous.decision.action,
    previousWorkflowKey: previous.decision.workflowKey,
    previousAnalysisPrompt: previous.decision.analysisPrompt || previousUser?.content,
    previousMessage: previous.content,
  }
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`status status-${status}`}>{status}</span>
}

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function PlanList({ plan }: { plan: PlannedStep[] }) {
  if (!plan.length) {
    return <p className="empty">No executable plan has been selected yet.</p>
  }

  return (
    <ol className="plan-list">
      {plan.map((step) => (
        <li key={step.id}>
          <strong>{step.title}</strong>
          <span>{step.description}</span>
          {(step.toolName || step.toolImage) && (
            <div className="tool-runtime">
              <small><b>Tool</b>{step.toolName || 'not specified'}</small>
              <small><b>Docker / Runtime</b>{step.toolImage || 'not specified'}</small>
            </div>
          )}
        </li>
      ))}
    </ol>
  )
}

function ExecutionTimeline({ events }: { events: TimelineEvent[] }) {
  if (!events.length) {
    return <p className="empty">Timeline events will appear while planning and execution progress.</p>
  }

  return (
    <ol className="timeline-list">
      {events.map((event) => (
        <li key={event.id} className={`timeline-item timeline-${event.status}`}>
          <div className="timeline-marker" />
          <div className="timeline-body">
            <div className="timeline-heading">
              <span>{event.title}</span>
              <StatusBadge status={event.status} />
            </div>
            <div className="timeline-meta">
              <span>{formatTime(event.timestamp)}</span>
              <span>{event.phase}</span>
              {event.toolName && <span>Tool: {event.toolName}</span>}
              {event.image && <span>Docker: {event.image}</span>}
              {typeof event.durationMs === 'number' && <span>{event.durationMs} ms</span>}
            </div>
            {event.detail && <p>{event.detail}</p>}
            {!!event.outputFiles?.length && (
              <small>Outputs: {event.outputFiles.map((file) => file.split('/').pop() || file).join(', ')}</small>
            )}
          </div>
        </li>
      ))}
    </ol>
  )
}

function CountsTable({ counts }: { counts: Record<string, Record<string, number>> }) {
  const samples = useMemo(() => {
    const firstGene = Object.values(counts)[0]
    return firstGene ? Object.keys(firstGene) : []
  }, [counts])

  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Gene</th>
            {samples.map((sample) => <th key={sample}>{sample}</th>)}
          </tr>
        </thead>
        <tbody>
          {Object.entries(counts).map(([gene, values]) => (
            <tr key={gene}>
              <td>{gene}</td>
              {samples.map((sample) => <td key={sample}>{values[sample] ?? 0}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function GenericTable({ table }: { table: NonNullable<TaskRecord['result']>['tables'][number] }) {
  return (
    <section>
      <h2>{table.title}</h2>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {table.columns.map((column) => <th key={column}>{column}</th>)}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, index) => (
              <tr key={index}>
                {table.columns.map((column) => <td key={column}>{row[column]}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function SampleDataBlock({ sampleData }: { sampleData: NonNullable<ModelPlan['sampleData']> }) {
  return (
    <div className="sample-data-block">
      <div>
        <strong>{sampleData.label}</strong>
        <span>{sampleData.status === 'included' ? 'Included in this repo' : 'Reference input shape'}</span>
      </div>
      <p>{sampleData.description}</p>
      <ul>
        {sampleData.files.map((file) => (
          <li key={file}>{file}</li>
        ))}
      </ul>
    </div>
  )
}

function formatJson(value: unknown) {
  return JSON.stringify(value, null, 2)
}

function displayReviewPath(value: string) {
  const marker = '.review-data/'
  const index = value.indexOf(marker)
  return index >= 0 ? value.slice(index) : value.split('/').pop() || value
}

function toolOriginLabel(origin: ReviewAgentRun['toolCalls'][number]['origin']) {
  if (origin === 'model_native') return 'Gemma native'
  if (origin === 'model_schema') return 'Gemma schema'
  if (origin === 'system_grounding') return 'System grounding'
  return 'JSON fallback'
}

function AgentEvidencePanel({ agentRun }: { agentRun?: ReviewAgentRun }) {
  // 中文：该面板把后端持久化的 Memory、Tool Calls 和 Trace 直接展示出来，方便评委验证原生函数调用和多步规划。
  // EN: This panel renders persisted Memory, Tool Calls, and Trace so reviewers can verify native function calling and multi-step planning.
  if (!agentRun) {
    return <p className="empty">Agent state will appear when analysis starts.</p>
  }

  const modeLabel = agentRun.mode === 'native_guided_tool_calling'
    ? 'Native controlled planner loop'
    : agentRun.mode === 'guided_tool_calling'
      ? 'Guided planner loop'
    : agentRun.mode === 'native_tool_calling'
      ? 'Native auto tool calling'
      : 'JSON fallback'

  return (
    <div className="agent-evidence">
      <div className="agent-mode-row">
        <span className={`agent-mode agent-mode-${agentRun.mode}`}>
          {modeLabel}
        </span>
        <span>{agentRun.model}</span>
      </div>

      <section>
        <h3>Memory</h3>
        <div className="agent-memory-grid">
          <div><strong>Workflow</strong><span>{agentRun.memory.selectedWorkflowName || agentRun.memory.selectedWorkflowKey || 'pending'}</span></div>
          <div><strong>Comparison</strong><span>{agentRun.memory.comparison || 'pending'}</span></div>
          <div><strong>Toy data</strong><span>{agentRun.memory.observedToyData.length} public files observed</span></div>
        </div>
        <div className="agent-memory-detail">
          <div>
            <strong>Observed public files</strong>
            {agentRun.memory.observedToyData.length ? (
              <ul className="agent-compact-list">
                {agentRun.memory.observedToyData.map((file) => <li key={file}>{file}</li>)}
              </ul>
            ) : (
              <p className="empty">No public sample files have been observed yet.</p>
            )}
          </div>
          <div>
            <strong>Recorded tool call IDs</strong>
            {agentRun.memory.toolCallIds.length ? (
              <ul className="agent-id-list">
                {agentRun.memory.toolCallIds.map((toolCallId) => <li key={toolCallId}>{toolCallId}</li>)}
              </ul>
            ) : (
              <p className="empty">No tool call IDs recorded yet.</p>
            )}
          </div>
        </div>
        <h3>Memory Rules</h3>
        <ul className="agent-compact-list">
          {agentRun.memory.publicSafetyRules.map((rule) => <li key={rule}>{rule}</li>)}
        </ul>
      </section>

      <section>
        <h3>Tool Calls</h3>
        {agentRun.toolCalls.length ? (
          <ol className="agent-tool-list">
            {agentRun.toolCalls.map((toolCall) => (
              <li key={toolCall.id} className={`agent-tool agent-tool-${toolCall.status}`}>
                <div>
                  <strong>{toolCall.name}</strong>
                  <span className={`tool-origin tool-origin-${toolCall.origin}`}>
                    {toolOriginLabel(toolCall.origin)}
                  </span>
                  <StatusBadge status={toolCall.status === 'requested' ? 'running' : toolCall.status} />
                </div>
                <small>{toolCall.id}</small>
                <pre>{formatJson(toolCall.arguments)}</pre>
                {toolCall.resultSummary && <p>{toolCall.resultSummary}</p>}
              </li>
            ))}
          </ol>
        ) : (
          <p className="empty">The local model did not return native tool calls; the workflow was grounded through the fallback planner.</p>
        )}
      </section>

      <section>
        <h3>Public Trace</h3>
        <ol className="agent-trace-list">
          {agentRun.trace.map((entry) => (
            <li key={entry.id} className={`trace-${entry.status}`}>
              <span>{entry.stage}</span>
              <strong>{entry.title}</strong>
              {entry.detail && <p>{entry.detail}</p>}
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}

function ReferencedFilesPanel({ workflow }: { workflow?: WorkflowView }) {
  if (!workflow) {
    return (
      <div className="request-files muted">
        <div>
          <strong>Referenced files</strong>
          <span>Pending selection</span>
        </div>
        <p>Select a preset to preview its public toy data, or send a natural-language request for Gemma 4 to draft the public tool-level plan.</p>
      </div>
    )
  }

  return (
    <div className="request-files">
      <div>
        <strong>Referenced files</strong>
        <span>Executable dataset</span>
      </div>
      <p>{workflow.sampleData.description}</p>
      <ul>
        {workflow.sampleData.files.map((file) => (
          <li key={file}>{file}</li>
        ))}
      </ul>
    </div>
  )
}

function TaskHistoryPanel({
  tasks,
  selectedTaskId,
  onSelect,
}: {
  tasks: TaskRecord[]
  selectedTaskId: string
  onSelect: (taskId: string) => void
}) {
  if (!tasks.length) {
    return <p className="empty">Completed and running workflow runs will appear here.</p>
  }

  return (
    <div className="run-history">
      {tasks.map((historyTask) => (
        <button
          key={historyTask.id}
          className={`run-history-item ${selectedTaskId === historyTask.id ? 'active' : ''}`}
          type="button"
          onClick={() => onSelect(historyTask.id)}
        >
          <span>
            <strong>{taskWorkflowName(historyTask)}</strong>
            <small>{shortTaskId(historyTask)} · {formatTime(historyTask.createdAt)}</small>
          </span>
          <StatusBadge status={historyTask.status} />
        </button>
      ))}
    </div>
  )
}

export default function App() {
  const [provider, setProvider] = useState<ProviderView | null>(null)
  const [prompt, setPrompt] = useState(defaultPrompt)
  const [selectedWorkflowKey, setSelectedWorkflowKey] = useState('bulk_rna_seq')
  const [workflows, setWorkflows] = useState<WorkflowView[]>([])
  const [plan, setPlan] = useState<PlannedStep[]>([])
  const [modelPlan, setModelPlan] = useState<ModelPlan | null>(null)
  const [task, setTask] = useState<TaskRecord | null>(null)
  const [taskHistory, setTaskHistory] = useState<TaskRecord[]>([])
  const [selectedTaskId, setSelectedTaskId] = useState('')
  const [busy, setBusy] = useState(false)
  const [runError, setRunError] = useState('')
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'Describe what you want to do. I can answer questions first, ask for missing details, or start a public workflow when you clearly ask me to run an analysis.',
    },
  ])
  const chatThreadRef = useRef<HTMLDivElement | null>(null)
  const progressPaneRef = useRef<HTMLElement | null>(null)
  const notifiedTaskRef = useRef('')
  const selectedTask = (selectedTaskId ? taskHistory.find((item) => item.id === selectedTaskId) : null)
    || (selectedTaskId && task?.id === selectedTaskId ? task : null)
  const visiblePlan = selectedTask?.plan || selectedTask?.result?.plan || plan
  const visibleModelPlan = selectedTask?.modelPlan || selectedTask?.result?.modelPlan || modelPlan
  const visibleAgentRun = selectedTask?.agentRun || selectedTask?.result?.agentRun || visibleModelPlan?.agentRun
  const visibleWorkflowKey = visibleModelPlan?.workflowKey || selectedTask?.result?.workflowKey || selectedWorkflowKey
  const selectedWorkflow = workflows.find((workflow) => workflow.key === visibleWorkflowKey)
  const taskRunning = task?.status === 'running'
  const analyzing = busy || taskRunning

  useEffect(() => {
    void api.getProvider().then((config) => {
      setProvider(config)
    })
    void api.getWorkflows().then((response) => {
      setWorkflows(response.workflows)
    })
  }, [])

  useEffect(() => {
    if (!task || task.status !== 'running') return
    const timer = window.setInterval(async () => {
      const latest = await api.getTask(task.id)
      setTask(latest)
      setTaskHistory((current) => upsertTaskHistory(current, latest))
      if (latest.status !== 'running') {
        window.clearInterval(timer)
      }
    }, 700)
    return () => window.clearInterval(timer)
  }, [task])

  useEffect(() => {
    const pane = progressPaneRef.current
    if (!pane || !selectedTask) return
    pane.scrollTo({ top: pane.scrollHeight, behavior: 'smooth' })
  }, [selectedTask?.id, selectedTask?.timeline.length, selectedTask?.status, selectedTask?.result])

  useEffect(() => {
    const pane = chatThreadRef.current
    if (!pane) return
    pane.scrollTo({ top: pane.scrollHeight, behavior: 'smooth' })
  }, [chatMessages.length])

  useEffect(() => {
    if (!task || task.status === 'running' || task.status === 'queued') return
    const notificationKey = `${task.id}:${task.status}`
    if (notifiedTaskRef.current === notificationKey) return

    if (task.status === 'completed' && task.result) {
      notifiedTaskRef.current = notificationKey
      const workflowName = task.modelPlan?.workflowName || task.result.modelPlan.workflowName || task.result.workflowKey
      const summary = task.result.summary || 'The workflow completed and the generated outputs are ready for review.'
      setChatMessages((current) => [
        ...current,
        {
          id: `assistant-result-${task.id}`,
          role: 'assistant',
          content: `Analysis completed for ${workflowName}. ${summary}`,
        },
      ])
      return
    }

    if (task.status === 'failed') {
      notifiedTaskRef.current = notificationKey
      setChatMessages((current) => [
        ...current,
        {
          id: `assistant-result-${task.id}`,
          role: 'assistant',
          content: `Analysis failed. ${task.error || 'Check the progress panel for details.'}`,
        },
      ])
    }
  }, [task?.id, task?.status, task?.result, task?.error, task?.modelPlan])

  async function runTask(analysisPrompt = prompt) {
    setBusy(true)
    setRunError('')
    setPlan([])
    setModelPlan(null)
    setTask(null)
    try {
      const created = await api.createTask(analysisPrompt)
      setTask(created)
      setSelectedTaskId(created.id)
      setTaskHistory((current) => upsertTaskHistory(current, created))
    } catch (error) {
      setRunError(error instanceof Error ? error.message : 'Task creation failed.')
    } finally {
      setBusy(false)
    }
  }

  async function sendConversationMessage() {
    const message = prompt.trim()
    if (!message || busy) return

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: message,
    }
    setChatMessages((current) => [...current, userMessage])
    setPrompt('')
    setBusy(true)
    setRunError('')

    try {
      const decision = await api.routeConversation(message, {
        hasActiveTask: taskRunning,
        latestTaskStatus: task?.status,
        ...previousConversationContext(chatMessages),
      })
      setChatMessages((current) => [
        ...current,
        {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: decision.message,
          decision,
        },
      ])
      if (decision.workflowKey) {
        setSelectedWorkflowKey(decision.workflowKey)
      }
      if (decision.action === 'run_analysis') {
        await runTask(decision.analysisPrompt || message)
      }
    } catch (error) {
      setRunError(error instanceof Error ? error.message : 'Conversation routing failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="app-shell">
      <section className="topbar">
        <div className="brand-lockup">
          <img
            className="brand-logo"
            src="/brand/xr-logo.png"
            alt="XR"
          />
          <div>
            <h1>
              <span>XR</span>
              <span className="brand-version">Lite Version for GDG Gemma 4 Hackathon 2026</span>
            </h1>
            <p>AI-powered Computational Biomedical Analysis Platform for Private Deployment</p>
          </div>
        </div>
        <div className="topbar-status">
          <Server size={18} />
          {provider?.model || 'Model not configured'}
        </div>
      </section>

      <section className="capability-strip">
        <div>
          <strong>Native Function Calling</strong>
          <span>Verified per run in Agent state: inspect the selected workflow tool call and arguments.</span>
        </div>
        <div>
          <strong>Memory + Tool Trace</strong>
          <span>Shown after execution with task memory, public tool calls, and planning trace records.</span>
        </div>
        <div>
          <strong>Reproducible Execution</strong>
          <span>Confirmed in Progress and results through Docker steps, outputs, tables, and report.</span>
        </div>
      </section>

      <section className="workspace">
        <aside className="left-pane">
          <div className="panel chat-panel">
            <div className="panel-title">
              <FlaskConical size={18} />
              Conversation
            </div>
            <div className="chat-thread" ref={chatThreadRef}>
              {chatMessages.map((message) => (
                <div
                  key={message.id}
                  className={`chat-message ${message.role === 'assistant' ? 'assistant-message' : 'user-message'}`}
                >
                  <strong>{message.role === 'assistant' ? 'Gemma 4 Agent' : 'You'}</strong>
                  <p>{message.content}</p>
                  {message.decision && (
                    <small className={`intent-badge intent-${message.decision.action}`}>
                      {message.decision.action.replace('_', ' ')}
                    </small>
                  )}
                </div>
              ))}
            </div>
            <form
              className="chat-composer"
              onSubmit={(event) => {
                event.preventDefault()
                if (!busy && prompt.trim()) {
                  void sendConversationMessage()
                }
              }}
            >
              <textarea
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key !== 'Enter' || event.ctrlKey) return
                  event.preventDefault()
                  if (!busy && prompt.trim()) {
                    void sendConversationMessage()
                  }
                }}
                placeholder="Ask Gemma 4 to plan an analysis..."
                rows={7}
              />
              <button type="submit" disabled={busy || !prompt.trim()} aria-label="Send analysis request">
                {busy ? <Loader2 className="spin" size={16} /> : <Send size={16} />}
                {busy ? 'Processing...' : 'Send'}
              </button>
            </form>
            {runError && <p className="error">{runError}</p>}
          </div>
          <p className="copyright">&copy; 2026 XR. Released under GPL-3.0-only.</p>
        </aside>

        <section className="middle-pane">
          <div className="panel">
            <div className="panel-title">
              <FlaskConical size={18} />
              Workflow presets
            </div>
            <div className="example-prompts">
              {promptExamples.map((example) => (
                <button
                  key={example.title}
                  className={`chip-button ${selectedWorkflowKey === example.workflowKey ? 'active' : ''}`}
                  type="button"
                  disabled={analyzing}
                  onClick={() => {
                    if (analyzing) return
                    setPrompt(example.prompt)
                    setSelectedWorkflowKey(example.workflowKey)
                    setSelectedTaskId('')
                    setPlan([])
                    setModelPlan(null)
                    setTask(null)
                    setRunError('')
                  }}
                >
                  <span>{example.title}</span>
                  <small>{example.description}</small>
                </button>
              ))}
            </div>
            <ReferencedFilesPanel workflow={selectedWorkflow} />
          </div>

          <div className="panel">
            <div className="panel-title">
              <Activity size={18} />
              Run history
            </div>
            <TaskHistoryPanel
              tasks={taskHistory}
              selectedTaskId={selectedTask?.id || ''}
              onSelect={setSelectedTaskId}
            />
          </div>

          <div className="panel">
            <div className="panel-title">
              <Workflow size={18} />
              Agent state
            </div>
            {selectedTask?.status === 'running' && <p className="planning-hint"><Loader2 className="spin" size={15} /> Planning and executing with the configured model endpoint...</p>}
            <AgentEvidencePanel agentRun={visibleAgentRun} />
          </div>

          <div className="panel">
            <div className="panel-title">
              <Database size={18} />
              Execution plan
            </div>
            <PlanList plan={visiblePlan} />
            {visibleModelPlan && (
              <div className="model-plan-meta">
                <div>
                  <strong>Plan source</strong>
                  {visibleModelPlan.source === 'model' ? 'Model generated' : visibleModelPlan.source === 'failed' ? 'Planning failed' : 'Fallback template'}
                </div>
                <div><strong>Model</strong>{visibleModelPlan.model}</div>
                {visibleModelPlan.workflowName && <div><strong>Workflow</strong>{visibleModelPlan.workflowName}</div>}
                {visibleModelPlan.executionMode && (
                  <div>
                    <strong>Mode</strong>
                    Executable demo
                  </div>
                )}
                <div><strong>Intent</strong>{visibleModelPlan.intent}</div>
                <div><strong>Comparison</strong>{visibleModelPlan.comparison}</div>
                {visibleModelPlan.sourceMessage && <div><strong>Source detail</strong>{visibleModelPlan.sourceMessage}</div>}
                {visibleModelPlan.executionNote && <div><strong>Execution note</strong>{visibleModelPlan.executionNote}</div>}
              </div>
            )}
            {visibleModelPlan?.sampleData && <SampleDataBlock sampleData={visibleModelPlan.sampleData} />}
          </div>
        </section>

        <section className="right-pane" ref={progressPaneRef}>
          <div className="panel">
            <div className="panel-title">
              <Activity size={18} />
              Progress and results
              {selectedTask && <StatusBadge status={selectedTask.status} />}
            </div>
            {!selectedTask && <p className="empty">Send a request from the conversation panel to plan and execute the workflow.</p>}
            {selectedTask?.error && <p className="error">{selectedTask.error}</p>}
            {selectedTask && (
              <section className="timeline-section">
                <h2>Live timeline</h2>
                <ExecutionTimeline events={selectedTask.timeline} />
              </section>
            )}
            {selectedTask?.result && (
              <div className="result-grid">
                <section>
                  <h2>Tool execution</h2>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Step</th>
                          <th>Image</th>
                          <th>Status</th>
                          <th>Duration</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedTask.result.toolRuns.map((run) => (
                          <tr key={run.id}>
                            <td>{run.name}</td>
                            <td>{run.image}</td>
                            <td>{run.status}</td>
                            <td>{run.durationMs} ms</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>

                {selectedTask.result.qc && (
                <section>
                  <h2>QC summary</h2>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Sample</th>
                          <th>Condition</th>
                          <th>Reads</th>
                          <th>Avg length</th>
                          <th>GC%</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedTask.result.qc.map((sample) => (
                          <tr key={sample.sampleId}>
                            <td>{sample.sampleId}</td>
                            <td>{sample.condition}</td>
                            <td>{sample.reads}</td>
                            <td>{sample.averageLength}</td>
                            <td>{sample.gcPercent}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
                )}

                {selectedTask.result.counts && (
                <section>
                  <h2>Count matrix</h2>
                  <CountsTable counts={selectedTask.result.counts} />
                </section>
                )}

                {selectedTask.result.differential && (
                <section>
                  <h2>Differential summary</h2>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Gene</th>
                          <th>Control mean</th>
                          <th>Treatment mean</th>
                          <th>log2FC</th>
                          <th>Direction</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedTask.result.differential.map((gene) => (
                          <tr key={gene.gene}>
                            <td>{gene.gene}</td>
                            <td>{gene.controlMean}</td>
                            <td>{gene.treatmentMean}</td>
                            <td>{gene.log2FoldChange}</td>
                            <td><span className={`direction direction-${gene.direction}`}>{formatDirection(gene.direction)}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
                )}

                {selectedTask.result.tables.map((table) => (
                  <GenericTable key={table.title} table={table} />
                ))}

                <section>
                  <h2>Report</h2>
                  <pre className="report">{selectedTask.result.reportMarkdown}</pre>
                  <p className="output-path">Output directory: {displayReviewPath(selectedTask.result.outputDir)}</p>
                </section>
              </div>
            )}
          </div>
        </section>
      </section>
    </main>
  )
}
