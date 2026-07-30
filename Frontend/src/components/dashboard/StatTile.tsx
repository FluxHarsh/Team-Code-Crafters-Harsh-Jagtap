import { cn, formatHours, formatRelative } from '@/lib/utils'
import { Link } from 'react-router-dom'
import type { GitHubState } from '@/types'
import type { ReactNode } from 'react'

// ─── StatTile ─────────────────────────────────────────────────────────────────

interface StatTileProps {
  label: string
  value: number | string
  icon?: string
  delta?: string
  accent?: 'primary' | 'success' | 'danger' | 'gold' | 'purple'
  className?: string
}

export function StatTile({ label, value, icon, delta, accent = 'primary', className }: StatTileProps) {
  const accentClass = {
    primary: 'text-primary',
    success: 'text-success',
    danger: 'text-danger',
    gold: 'text-gold',
    purple: 'text-purple',
  }[accent]

  return (
    <div className={cn('bg-white border border-border rounded-card p-4 shadow-card', className)}>
      <div className="flex items-start justify-between">
        <p className="text-xs font-600 text-muted">{label}</p>
        {icon && <span className="text-base">{icon}</span>}
      </div>
      <p className={cn('text-2xl font-800 mt-2 tracking-tight', accentClass)}>{value}</p>
      {delta && <p className="text-[10px] text-muted-2 mt-1">{delta}</p>}
    </div>
  )
}

// ─── SectionHeader ────────────────────────────────────────────────────────────

export function SectionHeader({
  title,
  action,
}: {
  title: string
  action?: ReactNode
}) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h2 className="text-sm font-700 text-navy">{title}</h2>
      {action}
    </div>
  )
}

// ─── CountdownCard ────────────────────────────────────────────────────────────

interface CountdownCardProps {
  hoursRemaining: number
  projectId: string
  pitchReady: boolean
}

export function CountdownCard({ hoursRemaining, projectId, pitchReady }: CountdownCardProps) {
  const isLow = hoursRemaining < 4
  const isCritical = hoursRemaining < 2

  return (
    <div
      className={cn(
        'rounded-card border p-4 shadow-card',
        isCritical
          ? 'bg-danger-soft border-red-200'
          : isLow
          ? 'bg-gold-soft border-yellow-200'
          : 'bg-white border-border'
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-700 uppercase tracking-wider text-muted-2">Time remaining</p>
          <p
            className={cn(
              'text-3xl font-800 tracking-tight mt-1 font-mono',
              isCritical ? 'text-danger' : isLow ? 'text-gold' : 'text-navy'
            )}
          >
            {formatHours(hoursRemaining)}
          </p>
          {isLow && !isCritical && (
            <p className="text-[11px] text-gold mt-1 font-600">⚠ Time is running low — focus on core demo</p>
          )}
          {isCritical && (
            <p className="text-[11px] text-danger mt-1 font-600">🔴 Critical — start pitch prep now</p>
          )}
        </div>

        {pitchReady && (
          <Link
            to={`/projects/${projectId}/dashboard/pitch`}
            className="flex items-center gap-1.5 text-xs font-700 bg-success text-white px-3 py-1.5 rounded-[9px] hover:bg-success-dark transition shadow-sm flex-none"
          >
            View Pitch →
          </Link>
        )}
      </div>

      <div className="mt-3">
        <div className="h-1.5 bg-black/10 rounded-full overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full transition-all',
              isCritical ? 'bg-danger' : isLow ? 'bg-gold' : 'bg-success'
            )}
            style={{ width: `${Math.min(100, (hoursRemaining / 24) * 100)}%` }}
          />
        </div>
      </div>
    </div>
  )
}

// ─── RepoActivityPanel ────────────────────────────────────────────────────────

interface RepoActivityPanelProps {
  githubState: GitHubState | null | undefined
  projectId: string
}

export function RepoActivityPanel({ githubState, projectId }: RepoActivityPanelProps) {
  if (!githubState) {
    return (
      <div className="flex flex-col items-center justify-center py-6 text-center">
        <span className="text-2xl mb-2">🔗</span>
        <p className="text-xs font-600 text-muted">No repo connected</p>
        <p className="text-[11px] text-muted-2 mt-0.5">Connect a GitHub repo to track commits, PRs, and issues</p>
        <Link
          to={`/projects/${projectId}/dashboard/agents/github_watcher`}
          className="mt-3 text-xs font-700 text-primary hover:text-primary-dark transition"
        >
          Connect a repo →
        </Link>
      </div>
    )
  }

  // branches is not returned by GET /github/state — only commits, open_prs, issues
  const stats = [
    { label: 'Commits', value: githubState.commits.length, icon: '📦' },
    { label: 'Open PRs', value: githubState.open_prs.length, icon: '🔀' },
    { label: 'Open Issues', value: githubState.issues.filter((i) => i.state === 'open').length, icon: '🎯' },
  ]

  return (
    <div>
      <div className="grid grid-cols-3 gap-2 mb-3">
        {stats.map((s) => (
          <div key={s.label} className="bg-bg rounded-[9px] p-2.5 text-center">
            <p className="text-base">{s.icon}</p>
            <p className="text-lg font-800 text-navy mt-0.5">{s.value}</p>
            <p className="text-[10px] text-muted-2 font-600">{s.label}</p>
          </div>
        ))}
      </div>
      {githubState.last_polled_at && (
        <p className="text-[10px] text-muted-2 text-center">
          Last polled {formatRelative(githubState.last_polled_at)}
        </p>
      )}
    </div>
  )
}