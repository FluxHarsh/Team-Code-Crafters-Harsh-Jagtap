import { useParams } from 'react-router-dom'
import { AGENT_MAP } from '@/lib/agents'
import { useStore } from '@/store'
import { cn } from '@/lib/utils'
import type { AgentNodeKey } from '@/types'

export function AgentPage() {
  const { agentKey } = useParams<{ agentKey: string }>()
  const activeNode = useStore((s) => s.activeNode)
  const recentRuns = useStore((s) => s.recentRuns)

  const agent = agentKey ? AGENT_MAP[agentKey as AgentNodeKey] : undefined

  if (!agent) {
    return <div className="p-8 text-sm text-muted">Unknown agent.</div>
  }

  const runs = recentRuns.filter((r) => r.node === agent.key)
  const isActive = activeNode === agent.key

  return (
    <div className="mx-auto max-w-2xl p-8">
      <div className="mb-6 flex items-center gap-3">
        <span className={cn('flex h-10 w-10 items-center justify-center rounded-full', agent.bgColor)}>
          <span className={cn('text-xs font-bold', agent.iconColor)}>{agent.shortLabel}</span>
        </span>
        <div>
          <h1 className="text-lg font-semibold text-text">{agent.label}</h1>
          <p className="text-xs text-muted">{agent.loop}</p>
        </div>
        {isActive && (
          <span className="ml-auto flex items-center gap-1.5 rounded-full bg-success-soft px-2.5 py-1 text-xs text-success">
            <span className="dot-live h-1.5 w-1.5 rounded-full" />
            Running
          </span>
        )}
      </div>

      <p className="mb-6 text-sm text-muted">{agent.desc}</p>

      <h2 className="mb-2 text-sm font-medium text-text">Recent runs</h2>
      <div className="space-y-2">
        {runs.map((run, i) => (
          <div key={i} className="flex items-center justify-between rounded-lg border border-border bg-card px-3 py-2 text-sm">
            <span className="text-text">{run.trigger}</span>
            <span className="text-xs text-muted">{new Date(run.finished_at).toLocaleTimeString()}</span>
          </div>
        ))}
        {runs.length === 0 && <p className="text-sm text-muted">No runs recorded yet.</p>}
      </div>
    </div>
  )
}
