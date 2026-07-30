import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '@/api'
import { formatHours } from '@/lib/utils'

export function DashboardSummaryBar({ projectId }: { projectId: string }) {
  const { data } = useQuery({
    queryKey: ['dashboard-summary', projectId],
    queryFn: () => dashboardApi.summary(projectId),
  })

  const s = data?.summary

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Stat label="Complete" value={s ? `${Math.round(s.percent_complete)}%` : '—'} />
      <Stat label="Building" value={s?.building_count ?? '—'} />
      <Stat label="Blocked" value={s?.blocked_count ?? '—'} accent="danger" />
      <Stat label="Shipped" value={s ? `${s.shipped_count}/${s.total_count}` : '—'} />
      <Stat label="Commits" value={s?.commit_count ?? '—'} />
      <Stat label="Hours left" value={s ? formatHours(s.hours_remaining) : '—'} />
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
