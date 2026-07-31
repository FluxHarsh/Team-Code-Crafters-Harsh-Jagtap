import { useParams } from 'react-router-dom'
import { useStore } from '@/store'
import { DashboardSummaryBar } from '@/components/dashboard/DashboardSummaryBar'
import { BuildDeckPanel } from '@/components/dashboard/BuildDeckPanel'
import { KanbanBoard } from '@/components/kanban/KanbanBoard'
import { RiskPanel } from '@/components/risks/RiskPanel'

export function OverviewPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const project = useStore((s) => s.project)

  if (!projectId || !project) return null

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-lg font-semibold text-text">Overview</h1>
        <p className="text-sm text-muted">{project.next_action ?? 'Everything on track.'}</p>
      </div>

      <DashboardSummaryBar projectId={projectId} />

      <BuildDeckPanel projectId={projectId} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <h2 className="mb-3 text-sm font-medium text-text">Roadmap</h2>
          <KanbanBoard />
        </div>
        <div>
          <h2 className="mb-3 text-sm font-medium text-text">Risks</h2>
          <RiskPanel risks={project.risks ?? []} />
        </div>
      </div>
    </div>
  )
}
