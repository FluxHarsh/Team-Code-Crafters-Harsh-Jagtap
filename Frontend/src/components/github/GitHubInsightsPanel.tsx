import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Info } from 'lucide-react'
import { githubInsightsApi } from '@/api'
import { useStore } from '@/store'

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
        {insights.map((insight, i) => (
          <div key={i} className="flex items-start gap-3 rounded-lg border border-border bg-card p-3">
            <span className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-info-soft text-info">
              <Info className="h-3.5 w-3.5" />
            </span>
            <p className="text-sm text-text">{insight}</p>
          </div>
        ))}
        {insights.length === 0 && <p className="text-sm text-muted">No insights yet.</p>}
      </div>
    </div>
  )
}
