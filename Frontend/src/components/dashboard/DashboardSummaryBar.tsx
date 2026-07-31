import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '@/api'
import { formatHours } from '@/lib/utils'

export function DashboardSummaryBar({ projectId }: { projectId: string }) {
  const { data: overview } = useQuery({
    queryKey: ['dashboard-overview', projectId],
    queryFn: () => dashboardApi.overview(projectId),
  })

  const { data: kanban } = useQuery({
    queryKey: ['dashboard-kanban', projectId],
    queryFn: () => dashboardApi.kanban(projectId),
  })

  const counts = kanban?.summary.counts

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Stat label="Complete" value={overview ? `${Math.round(overview.percent_complete)}%` : '—'} />
      <Stat label="Building" value={counts?.building ?? '—'} />
      <Stat label="Blocked" value={counts?.blocked ?? '—'} accent="danger" />
      <Stat label="Shipped" value={kanban ? `${kanban.summary.shipped_count}/${kanban.summary.total_tasks}` : '—'} />
      <Stat label="Commits" value={kanban?.summary.commit_count ?? '—'} />
      <Stat label="Hours left" value={overview?.hours_remaining != null ? formatHours(overview.hours_remaining) : '—'} />
    </div>
  )
}

function Stat({ label, value, accent }: { label: string; value: string | number; accent?: 'danger' }) {
  return (
    <div className="rounded-card border border-border bg-card p-3">
      <p className="text-xs text-muted">{label}</p>
      <p className={`mt-1 text-xl font-semibold ${accent === 'danger' ? 'text-danger' : 'text-text'}`}>{value}</p>
    </div>
  )
}
