import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Info, ShieldAlert } from 'lucide-react'
import { githubInsightsApi } from '@/api'
import { useStore } from '@/store'
import { formatRelative, cn } from '@/lib/utils'
import type { GitHubInsight } from '@/types'

const SEVERITY_ICON: Record<NonNullable<GitHubInsight['severity']>, typeof Info> = {
  info: Info,
  warn: AlertTriangle,
  critical: ShieldAlert,
}

const SEVERITY_COLOR: Record<NonNullable<GitHubInsight['severity']>, string> = {
  info: 'text-info bg-info-soft',
  warn: 'text-gold bg-gold-soft',
  critical: 'text-danger bg-danger-soft',
}

export function GitHubInsightsPanel({ projectId }: { projectId: string }) {
  const insights = useStore((s) => s.githubInsights)
  const setGithubInsights = useStore((s) => s.setGithubInsights)

  const { data } = useQuery({
    queryKey: ['github-insights', projectId],
    queryFn: () => githubInsightsApi.list(projectId),
  })

  useEffect(() => {
    if (data) setGithubInsights(data.insights)
  }, [data, setGithubInsights])

  return (
    <div className="mx-auto max-w-2xl p-8">
      <h1 className="mb-1 text-lg font-semibold text-text">GitHub Insights</h1>
      <p className="mb-6 text-sm text-muted">Patterns the GitHub Watcher noticed across commits and PRs.</p>

      <div className="space-y-2">
        {insights.map((insight) => {
          const severity = insight.severity ?? 'info'
          const Icon = SEVERITY_ICON[severity]
          return (
            <div key={insight.id} className="flex items-start gap-3 rounded-lg border border-border bg-card p-3">
              <span className={cn('flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full', SEVERITY_COLOR[severity])}>
                <Icon className="h-3.5 w-3.5" />
              </span>
              <div className="flex-1">
                <p className="text-sm text-text">{insight.summary}</p>
                <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-2">
                  {insight.related_task && <span>on “{insight.related_task}”</span>}
                  <span>{formatRelative(insight.created_at)}</span>
                </div>
              </div>
            </div>
          )
        })}
        {insights.length === 0 && <p className="text-sm text-muted">No insights yet.</p>}
      </div>
    </div>
  )
}
