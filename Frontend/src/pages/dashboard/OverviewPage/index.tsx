import { useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useStore } from '@/store'
import { useProject } from '@/hooks/useProject'
import { roadmapApi, risksApi, agentGraphApi } from '@/api'
import { useEffect } from 'react'
import { KanbanBoard } from '@/components/kanban/KanbanBoard'
import { RiskFeedItem } from '@/components/risks/RiskFeedItem'
import { AgentGraphView } from '@/components/dashboard/AgentGraphView'
import { StatTile, SectionHeader, CountdownCard, RepoActivityPanel } from '@/components/dashboard/StatTile'
import { SkeletonCard, EmptyState } from '@/components/ui'
import { AGENT_LIST, AGENT_MAP } from '@/lib/agents'
import { formatRelative, cn } from '@/lib/utils'
import { useStore as useZustand } from '@/store'
import type { RoadmapTask } from '@/types'

export function OverviewPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: project, isLoading } = useProject(projectId)
  const { agentGraph, setAgentGraph, updateTask } = useStore()
  const queryClient = useQueryClient()

  // Load agent graph state on mount
  useEffect(() => {
    if (!projectId) return
    agentGraphApi.getState(projectId).then(setAgentGraph).catch(() => {})
  }, [projectId, setAgentGraph])

  const handleTaskMove = async (taskId: string, newStatus: RoadmapTask['status']) => {
    if (!projectId) return
    // Optimistic update
    const task = project?.roadmap?.find((t) => t.id === taskId)
    if (task) updateTask({ ...task, status: newStatus })

    try {
      await roadmapApi.updateTask(projectId, taskId, { status: newStatus })
    } catch {
      // Revert
      if (task) updateTask(task)
      throw new Error('Failed to move task')
    }
  }

  const handleResolveRisk = async (riskId: string, note: string) => {
    if (!projectId) return
    await risksApi.resolve(projectId, riskId, note)
    queryClient.invalidateQueries({ queryKey: ['project', projectId] })
  }

  const handleReprioritize = async (riskId: string) => {
    if (!projectId) return
    await risksApi.reprioritize(projectId, riskId)
    queryClient.invalidateQueries({ queryKey: ['project', projectId] })
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => <SkeletonCard key={i} />)}
        </div>
        <SkeletonCard />
        <SkeletonCard />
      </div>
    )
  }

  if (!project) return null

  const roadmap = project.roadmap ?? []
  const risks = project.risks ?? []
  const openRisks = risks.filter((r) => !r.resolved)
  const doneCount = roadmap.filter((t) => t.status === 'done').length
  const totalCommits = project.github_state?.commits.length ?? 0

  return (
    <div className="space-y-6 max-w-[1200px]">
      {/* Stat tiles */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile label="Total tasks" value={roadmap.length} icon="📋" accent="primary" />
        <StatTile
          label="Completed"
          value={doneCount}
          icon="✅"
          accent="success"
          delta={`${roadmap.length > 0 ? Math.round((doneCount / roadmap.length) * 100) : 0}% done`}
        />
        <StatTile
          label="Open risks"
          value={openRisks.length}
          icon="⚠️"
          accent={openRisks.length > 0 ? 'danger' : 'success'}
        />
        <StatTile label="Commits tracked" value={totalCommits} icon="📦" accent="purple" />
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Left: Kanban + Risks */}
        <div className="xl:col-span-2 space-y-6">
          {/* Kanban */}
          <div className="bg-white border border-border rounded-card shadow-card p-4">
            <SectionHeader
              title="Kanban Board"
              action={
                <button
                  onClick={() => {
                    if (!projectId) return
                    roadmapApi.replan(projectId).then(() =>
                      queryClient.invalidateQueries({ queryKey: ['project', projectId] })
                    ).catch(() => {})
                  }}
                  className="text-xs font-600 text-primary hover:text-primary-dark transition"
                >
                  Re-plan
                </button>
              }
            />
            {roadmap.length === 0 ? (
              <EmptyState
                icon="📋"
                title="No tasks yet"
                description="Tasks will appear here once the plan is approved and the Planner builds your roadmap."
              />
            ) : (
              <KanbanBoard tasks={roadmap} onTaskMove={handleTaskMove} />
            )}
          </div>

          {/* Risk feed */}
          <div className="bg-white border border-border rounded-card shadow-card p-4">
            <SectionHeader title="Risk Feed" />
            {openRisks.length === 0 ? (
              <EmptyState icon="🛡️" title="No active risks" description="The Risk Watcher is monitoring your project. Risks will appear here when flagged." />
            ) : (
              <div className="space-y-2.5">
                {openRisks.map((risk) => (
                  <RiskFeedItem
                    key={risk.id}
                    risk={risk}
                    onResolve={handleResolveRisk}
                    onReprioritize={handleReprioritize}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Agent graph + GitHub + Countdown + Agents at a glance */}
        <div className="space-y-4">
          {/* Countdown */}
          <CountdownCard
            hoursRemaining={project.hours_remaining}
            projectId={projectId!}
            pitchReady={!!project.pitch_outline}
          />

          {/* Agent graph */}
          <div className="bg-white border border-border rounded-card shadow-card p-4">
            <SectionHeader title="Agent Graph" />
            <AgentGraphView />
          </div>

          {/* GitHub */}
          <div className="bg-white border border-border rounded-card shadow-card p-4">
            <SectionHeader title="Repo Activity" />
            <RepoActivityPanel
              githubState={project.github_state}
              projectId={projectId!}
            />
          </div>

          {/* Agents at a glance */}
          <div className="bg-white border border-border rounded-card shadow-card p-4">
            <SectionHeader title="Agents" />
            <div className="space-y-2">
              {AGENT_LIST.map((agent) => {
                const isLive = agentGraph.active_node === agent.key
                const lastRun = agentGraph.recent_runs.find((r) => r.node === agent.key)
                return (
                  <div key={agent.key} className="flex items-center gap-2.5">
                    <div className={cn('w-5 h-5 rounded-[6px] text-[8px] font-800 flex items-center justify-center flex-none', agent.bgColor, agent.iconColor)}>
                      {agent.shortLabel}
                    </div>
                    <span className={cn('text-[11px] flex-1 truncate', isLive ? 'font-700 text-navy' : 'font-500 text-muted')}>
                      {agent.label}
                    </span>
                    {isLive ? (
                      <span className="text-[10px] font-700 text-success-dark flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full dot-live" /> Live
                      </span>
                    ) : lastRun ? (
                      <span className="text-[10px] text-muted-2 font-mono">
                        {formatRelative(lastRun.finished_at)}
                      </span>
                    ) : (
                      <span className="text-[10px] text-muted-2">—</span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
