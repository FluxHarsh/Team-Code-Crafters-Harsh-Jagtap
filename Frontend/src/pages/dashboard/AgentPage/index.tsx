import { useParams } from 'react-router-dom'
import { useState } from 'react'
import { useStore } from '@/store'
import { AGENT_MAP } from '@/lib/agents'
import { useProject } from '@/hooks/useProject'
import { githubApi, risksApi, pitchApi } from '@/api'
import { useQueryClient } from '@tanstack/react-query'
import { formatRelative, cn } from '@/lib/utils'
import { RiskFeedItem } from '@/components/risks/RiskFeedItem'
import { StatusDot, EmptyState, Button, Input, InlineError, Card } from '@/components/ui'
import type { AgentNodeKey } from '@/types'

// ─── Agent Run Log ─────────────────────────────────────────────────────────────

function AgentRunLog({ agentKey }: { agentKey: AgentNodeKey }) {
  const runs = useStore((s) =>
    s.agentGraph.recent_runs.filter((r) => r.node === agentKey)
  )
  if (runs.length === 0)
    return <p className="text-xs text-muted-2 py-2">No runs recorded yet.</p>

  return (
    <div className="space-y-1.5 max-h-48 overflow-y-auto">
      {runs.map((run, i) => (
        <div key={i} className="flex items-center gap-2 text-xs border-b border-border-soft pb-1.5">
          <span className={cn('w-1.5 h-1.5 rounded-full flex-none', run.status === 'failed' ? 'bg-danger' : 'bg-success')} />
          <span className="font-600 text-navy capitalize">{run.trigger.replace(/_/g, ' ')}</span>
          <span className="ml-auto text-[10px] font-mono text-muted-2">{formatRelative(run.finished_at)}</span>
        </div>
      ))}
    </div>
  )
}

// ─── Agent Page Header ─────────────────────────────────────────────────────────

function AgentPageHeader({ agentKey }: { agentKey: AgentNodeKey }) {
  const meta = AGENT_MAP[agentKey]
  const isLive = useStore((s) => s.agentGraph.active_node === agentKey)
  if (!meta) return null
  return (
    <div className="flex items-start gap-4 mb-6">
      <div className={cn('w-12 h-12 rounded-[12px] flex items-center justify-center text-sm font-800 flex-none', meta.bgColor, meta.iconColor)}>
        {meta.shortLabel}
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <h1 className="text-lg font-800 text-navy">{meta.label}</h1>
          <StatusDot live={isLive} />
          {isLive && <span className="text-[10px] font-700 text-success-dark">Running</span>}
        </div>
        <p className="text-sm text-muted mt-0.5">{meta.desc}</p>
        <span className="inline-block text-[10px] font-700 bg-border text-muted px-2 py-0.5 rounded-full mt-1">
          {meta.loop}
        </span>
      </div>
    </div>
  )
}

// ─── GitHub connect form ───────────────────────────────────────────────────────

function GitHubConnectForm({ projectId }: { projectId: string }) {
  const [repo, setRepo] = useState('')
  const [token, setToken] = useState('')
  const [interval, setInterval] = useState('120')
  const [loading, setLoading] = useState(false)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const handleConnect = async () => {
    setLoading(true)
    setError(null)
    try {
      await githubApi.connect(projectId, {
        repo_full_name: repo,
        access_token: token,
        poll_interval_seconds: parseInt(interval),
      })
      setConnected(true)
      queryClient.invalidateQueries({ queryKey: ['project', projectId] })
    } catch (e: any) {
      if (e.status === 401) setError('Invalid GitHub token — check it has repo:read scope.')
      else if (e.status === 422) setError('Repo not found or no access — check the repo name and token.')
      else setError(e.message ?? 'Connection failed')
    } finally {
      setLoading(false)
    }
  }

  if (connected) {
    return (
      <div className="bg-success-soft border border-green-200 rounded-[10px] p-4 text-center">
        <p className="text-sm font-700 text-success-dark">✓ Connected!</p>
        <p className="text-xs text-success-dark/70 mt-1">Polling every {interval}s. GitHub Watcher is now active.</p>
      </div>
    )
  }

  return (
    <div className="space-y-3 max-w-sm">
      <p className="text-xs text-muted">Connect a GitHub repo to track commits, PRs, and issues in real time.</p>
      <Input label="Repo full name" placeholder="team/hackpilot" value={repo} onChange={(e) => setRepo(e.target.value)} />
      <Input label="Personal access token" type="password" placeholder="ghp_…" value={token} onChange={(e) => setToken(e.target.value)} />
      <div className="space-y-1">
        <label className="text-xs font-600 text-muted">Poll interval</label>
        <select
          value={interval}
          onChange={(e) => setInterval(e.target.value)}
          className="w-full border border-border rounded-[9px] px-3 py-2 text-sm text-text bg-white outline-none focus:border-primary"
        >
          <option value="60">60s</option>
          <option value="120">120s (recommended)</option>
          <option value="300">5 min</option>
        </select>
      </div>
      <InlineError message={error} />
      <Button onClick={handleConnect} loading={loading} disabled={!repo || !token} className="w-full">
        Connect repo
      </Button>
    </div>
  )
}

// ─── Dependency Graph Placeholder ─────────────────────────────────────────────

function DependencyGraphView({ projectId }: { projectId: string }) {
  const project = useStore((s) => s.project)
  const roadmap = project?.roadmap ?? []
  if (roadmap.length === 0)
    return <EmptyState icon="🕸️" title="No milestones yet" description="Build your roadmap first." />

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${Math.max(400, roadmap.length * 100)} 180`} className="w-full">
        {roadmap.map((task, i) => {
          const x = 60 + i * 100
          const y = 80
          const nextTask = roadmap[i + 1]
          return (
            <g key={task.id}>
              {nextTask && (
                <line x1={x + 24} y1={y} x2={x + 76} y2={y} stroke="#ECEEF5" strokeWidth="2" markerEnd="url(#arrow)" />
              )}
              <circle cx={x} cy={y} r={22}
                fill={task.status === 'done' ? '#1FAE59' : task.status === 'blocked' ? '#F0464B' : task.status === 'in_progress' ? '#7C5CFC' : '#F6F7FB'}
                stroke={task.status === 'done' ? '#178C48' : '#ECEEF5'} strokeWidth="1.5"
              />
              <text x={x} y={y + 4} textAnchor="middle" fontSize="8" fill={task.status === 'done' || task.status === 'blocked' || task.status === 'in_progress' ? '#fff' : '#7C88A6'} fontWeight="700">
                {i + 1}
              </text>
              <text x={x} y={y + 38} textAnchor="middle" fontSize="7.5" fill="#7C88A6" fontWeight="600">
                {task.task.split(' ').slice(0, 3).join(' ')}
              </text>
            </g>
          )
        })}
        <defs>
          <marker id="arrow" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
            <path d="M0,0 L0,6 L6,3 z" fill="#ECEEF5" />
          </marker>
        </defs>
      </svg>
    </div>
  )
}

// ─── Agent-specific panels ────────────────────────────────────────────────────

function SupervisorPanel() {
  const runs = useStore((s) => s.agentGraph.recent_runs)
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted leading-relaxed">
        The Supervisor doesn't do the work itself — it reads the current project state (status, hours remaining, open risks) and decides which agent to call next. Routing is conditional, not fixed.
      </p>
      <div className="space-y-1.5">
        {runs.length === 0 ? (
          <p className="text-xs text-muted-2">No routing decisions yet.</p>
        ) : (
          runs.map((run, i) => (
            <div key={i} className="flex items-center gap-2 text-xs bg-bg rounded-[8px] px-3 py-2">
              {i > 0 && <span className="text-muted-2">→</span>}
              <span className="font-700 text-navy">{run.node.replace(/_/g, ' ')}</span>
              <span className="text-muted-2 text-[10px] ml-auto">via {run.trigger}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function PlannerPanel({ projectId }: { projectId: string }) {
  const project = useStore((s) => s.project)
  const roadmap = project?.roadmap ?? []
  const done = roadmap.filter((t) => t.status === 'done').length
  const pct = roadmap.length > 0 ? Math.round((done / roadmap.length) * 100) : 0

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-center justify-between text-xs mb-2">
          <span className="font-600 text-muted">Completion</span>
          <span className="font-800 text-navy">{pct}%</span>
        </div>
        <div className="h-2 bg-bg rounded-full overflow-hidden border border-border">
          <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>
      <div className="space-y-1.5">
        {roadmap.map((task) => (
          <div key={task.id} className={cn('flex items-center gap-2.5 text-xs rounded-[8px] px-3 py-2 border',
            task.status === 'done' && 'bg-success-soft border-green-200',
            task.status === 'blocked' && 'bg-danger-soft border-red-200',
            task.status === 'in_progress' && 'bg-purple-soft/30 border-purple/20',
            task.status === 'todo' && 'bg-white border-border'
          )}>
            <span className={cn('w-1.5 h-1.5 rounded-full flex-none',
              task.status === 'done' && 'bg-success',
              task.status === 'blocked' && 'bg-danger',
              task.status === 'in_progress' && 'bg-purple',
              task.status === 'todo' && 'bg-muted-2'
            )} />
            <span className={cn('flex-1 font-600', task.status === 'done' && 'line-through text-muted', task.status !== 'done' && 'text-navy')}>
              {task.task}
            </span>
            <span className="text-muted-2 text-[10px]">{task.owner}</span>
          </div>
        ))}
        {roadmap.length === 0 && <p className="text-xs text-muted-2">No tasks yet.</p>}
      </div>
    </div>
  )
}

function RiskPanel({ projectId }: { projectId: string }) {
  const project = useStore((s) => s.project)
  const queryClient = useQueryClient()
  const risks = project?.risks ?? []

  const handleResolve = async (riskId: string, note: string) => {
    await risksApi.resolve(projectId, riskId, note)
    queryClient.invalidateQueries({ queryKey: ['project', projectId] })
  }

  const handleReprioritize = async (riskId: string) => {
    await risksApi.reprioritize(projectId, riskId)
    queryClient.invalidateQueries({ queryKey: ['project', projectId] })
  }

  return risks.length === 0 ? (
    <EmptyState icon="🛡️" title="No risks flagged" description="The watcher is running. Risks will appear here when detected." />
  ) : (
    <div className="space-y-2.5">
      {risks.map((risk) => (
        <RiskFeedItem key={risk.id} risk={risk} onResolve={handleResolve} onReprioritize={handleReprioritize} />
      ))}
    </div>
  )
}

function PitchPanel({ projectId }: { projectId: string }) {
  const project = useStore((s) => s.project)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const handleGenerate = async () => {
    setGenerating(true)
    setError(null)
    try {
      await pitchApi.generate(projectId)
      queryClient.invalidateQueries({ queryKey: ['project', projectId] })
    } catch (e: any) {
      if (e.status === 409) setError('Roadmap not far enough along yet — complete more tasks first.')
      else setError(e.message ?? 'Generation failed')
    } finally {
      setGenerating(false)
    }
  }

  const pitch = project?.pitch_outline
  if (!pitch) {
    return (
      <div className="text-center space-y-3 py-4">
        <p className="text-2xl">🎤</p>
        <p className="text-sm font-600 text-muted">No pitch generated yet</p>
        <p className="text-xs text-muted-2">The Pitch Agent auto-triggers when the roadmap is &gt;80% done. Or trigger it manually.</p>
        <InlineError message={error} />
        <Button onClick={handleGenerate} loading={generating}>Generate pitch</Button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {[
        { label: 'Problem', value: pitch.problem },
        { label: 'Solution', value: pitch.solution },
        { label: 'Differentiator', value: pitch.differentiator },
      ].map((s) => (
        <div key={s.label}>
          <p className="text-[10px] font-700 uppercase tracking-wider text-muted-2 mb-1">{s.label}</p>
          <p className="text-sm text-navy leading-relaxed">{s.value}</p>
        </div>
      ))}
      {pitch.demo_flow?.length > 0 && (
        <div>
          <p className="text-[10px] font-700 uppercase tracking-wider text-muted-2 mb-1.5">Demo flow</p>
          <ol className="space-y-1">
            {pitch.demo_flow.map((step, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-navy">
                <span className="w-4 h-4 rounded-full bg-primary-soft text-primary-dark text-[9px] font-800 flex items-center justify-center flex-none mt-0.5">{i + 1}</span>
                {step}
              </li>
            ))}
          </ol>
        </div>
      )}
      <Button variant="secondary" size="sm" onClick={handleGenerate} loading={generating}>Regenerate</Button>
    </div>
  )
}

// ─── Main Agent Page ───────────────────────────────────────────────────────────

export function AgentPage() {
  const { projectId, agentKey } = useParams<{ projectId: string; agentKey: string }>()
  const { isLoading } = useProject(projectId)
  const project = useStore((s) => s.project)
  const meta = AGENT_MAP[agentKey ?? '']

  if (!meta) {
    return <div className="text-sm text-muted">Agent "{agentKey}" not found.</div>
  }

  return (
    <div className="max-w-3xl space-y-6">
      <AgentPageHeader agentKey={agentKey as AgentNodeKey} />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Agent-specific panel */}
        <div className="bg-white border border-border rounded-card shadow-card p-4 md:col-span-2">
          <p className="text-xs font-700 text-navy mb-3">
            {agentKey === 'supervisor' && 'Recent routing decisions'}
            {agentKey === 'intake' && 'Intake summary'}
            {agentKey === 'scope_critic' && 'Scope — kept vs cut'}
            {agentKey === 'planner' && 'Roadmap progress'}
            {agentKey === 'github_watcher' && 'GitHub integration'}
            {agentKey === 'risk_watcher' && 'All flagged risks'}
            {agentKey === 'reprioritizer' && 'Dependency graph'}
            {agentKey === 'pitch_agent' && 'Generated pitch'}
          </p>

          {agentKey === 'supervisor' && <SupervisorPanel />}
          {agentKey === 'intake' && (
            <div className="space-y-3">
              {project?.project_idea ? (
                <>
                  <div><p className="text-[10px] font-700 uppercase tracking-wider text-muted-2 mb-1">Raw idea</p><p className="text-sm text-navy">{project.project_idea.raw}</p></div>
                  {project.project_idea.refined && <div><p className="text-[10px] font-700 uppercase tracking-wider text-muted-2 mb-1">Refined</p><p className="text-sm text-navy">{project.project_idea.refined}</p></div>}
                </>
              ) : <p className="text-xs text-muted-2">No intake data yet.</p>}
            </div>
          )}
          {agentKey === 'scope_critic' && (
            <div className="space-y-3">
              {project?.scope ? (
                <>
                  <div>
                    <p className="text-[10px] font-700 uppercase tracking-wider text-muted-2 mb-1.5">MVP features</p>
                    <div className="flex flex-wrap gap-1.5">{project.scope.mvp_features.map((f, i) => <span key={i} className="text-xs font-600 bg-success-soft border border-green-200 text-success-dark px-2 py-0.5 rounded-[6px]">{f}</span>)}</div>
                  </div>
                  <div>
                    <p className="text-[10px] font-700 uppercase tracking-wider text-muted-2 mb-1.5">Cut</p>
                    <div className="flex flex-wrap gap-1.5">{project.scope.cut_features.map((f, i) => <span key={i} className="text-xs font-600 bg-border text-muted-2 px-2 py-0.5 rounded-[6px] line-through">{f}</span>)}</div>
                  </div>
                </>
              ) : <p className="text-xs text-muted-2">No scope data yet.</p>}
            </div>
          )}
          {agentKey === 'planner' && <PlannerPanel projectId={projectId!} />}
          {agentKey === 'github_watcher' && (
            <div className="space-y-4">
              {!project?.github_state ? (
                <GitHubConnectForm projectId={projectId!} />
              ) : (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="dot-live w-2 h-2 rounded-full" />
                    <span className="text-xs font-700 text-success-dark">Polling active</span>
                    {project.github_state.last_polled_at && (
                      <span className="text-[10px] text-muted-2 ml-auto">Last poll: {formatRelative(project.github_state.last_polled_at)}</span>
                    )}
                  </div>
                  <p className="text-[11px] text-muted">Every poll: fetch recent commits, map to roadmap milestones, check open PRs, flag stale branches and ETA breaches.</p>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { l: 'Commits', v: project.github_state.commits.length },
                      { l: 'Open PRs', v: project.github_state.open_prs.length },
                      { l: 'Issues', v: project.github_state.issues.length },
                      { l: 'Branches', v: project.github_state.branches.length },
                    ].map((s) => (
                      <div key={s.l} className="bg-bg rounded-[9px] p-2.5 text-center">
                        <p className="text-lg font-800 text-navy">{s.v}</p>
                        <p className="text-[10px] text-muted-2 font-600">{s.l}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          {agentKey === 'risk_watcher' && <RiskPanel projectId={projectId!} />}
          {agentKey === 'reprioritizer' && (
            <div className="space-y-4">
              <p className="text-xs text-muted">When a risk is flagged, the Reprioritizer uses Neo4j to traverse the dependency graph — "if I fix this milestone, what does it unblock downstream?" — before suggesting a fix.</p>
              <DependencyGraphView projectId={projectId!} />
            </div>
          )}
          {agentKey === 'pitch_agent' && <PitchPanel projectId={projectId!} />}
        </div>

        {/* Run log */}
        <div className="bg-white border border-border rounded-card shadow-card p-4">
          <p className="text-xs font-700 text-navy mb-3">Recent runs</p>
          <AgentRunLog agentKey={agentKey as AgentNodeKey} />
        </div>

        {/* Loop info */}
        <div className="bg-white border border-border rounded-card shadow-card p-4">
          <p className="text-xs font-700 text-navy mb-2">About this agent</p>
          <p className="text-xs text-muted leading-relaxed">{meta.desc}</p>
          <div className="mt-3 flex items-center gap-1.5">
            <span className="text-[10px] font-700 bg-border text-muted px-2 py-0.5 rounded-full">{meta.loop}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
