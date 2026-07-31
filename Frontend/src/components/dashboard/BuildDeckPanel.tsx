import { useRef, useState, useLayoutEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '@/api'
import { formatHours, cn } from '@/lib/utils'
import type { RoadmapTask } from '@/types'

// Build Deck — live workflow board (Part 2 of the todo plan).
// Replaces the removed Agent Graph card. Driven by real roadmap/commit/hours
// data (project.roadmap, project.github_state.commits.length,
// project.hours_remaining) via GET /projects/{id}/dashboard(/kanban).
//
// Connector lines: dependency edges (`RoadmapTask.depends_on`) are drawn
// between a task and each task it depends on, whenever both are present on
// the board. If the backend doesn't yet populate `depends_on` for a given
// task, no line is drawn for it — see plan step 4, option (a)/(b): we degrade
// gracefully to "no lines" rather than guessing relationships.

const COLUMNS: { id: RoadmapTask['status']; label: string; dot: string; badgeText: string }[] = [
  { id: 'todo', label: 'Queued', dot: 'bg-muted-2', badgeText: 'text-muted' },
  { id: 'in_progress', label: 'Building', dot: 'bg-purple', badgeText: 'text-purple' },
  { id: 'blocked', label: 'Blocked', dot: 'bg-danger', badgeText: 'text-danger' },
  { id: 'done', label: 'Shipped', dot: 'bg-success', badgeText: 'text-success' },
]

const COLUMN_LINE_COLOR: Record<string, string> = {
  todo: '#A8B0C4',
  in_progress: '#7C5CFC',
  blocked: '#F0464B',
  done: '#1FAE59',
}

interface Point {
  x: number
  y: number
}

interface ConnectorLine {
  from: Point
  to: Point
  color: string
}

export function BuildDeckPanel({ projectId }: { projectId: string }) {
  const { data } = useQuery({
    queryKey: ['dashboard-kanban', projectId],
    queryFn: () => dashboardApi.kanban(projectId),
  })

  const roadmap = data?.roadmap ?? []
  const summary = data?.summary

  const containerRef = useRef<HTMLDivElement>(null)
  const cardRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const [lines, setLines] = useState<ConnectorLine[]>([])

  const registerCard = (id: string) => (el: HTMLDivElement | null) => {
    if (el) cardRefs.current.set(id, el)
    else cardRefs.current.delete(id)
  }

  useLayoutEffect(() => {
    function computeLines() {
      const container = containerRef.current
      if (!container) return
      const containerRect = container.getBoundingClientRect()
      const next: ConnectorLine[] = []

      for (const task of roadmap) {
        if (!task.depends_on?.length) continue
        const fromEl = cardRefs.current.get(task.id)
        if (!fromEl) continue
        const fromRect = fromEl.getBoundingClientRect()

        for (const depId of task.depends_on) {
          const toEl = cardRefs.current.get(depId)
          if (!toEl) continue
          const toRect = toEl.getBoundingClientRect()

          // Connect the edge of each card that faces the other, so lines run
          // horizontally between columns rather than through card bodies.
          const fromLeft = fromRect.left < toRect.left
          const from: Point = {
            x: (fromLeft ? fromRect.right : fromRect.left) - containerRect.left,
            y: fromRect.top + fromRect.height / 2 - containerRect.top,
          }
          const to: Point = {
            x: (fromLeft ? toRect.left : toRect.right) - containerRect.left,
            y: toRect.top + toRect.height / 2 - containerRect.top,
          }

          next.push({ from, to, color: COLUMN_LINE_COLOR[task.status] ?? '#A8B0C4' })
        }
      }
      setLines(next)
    }

    computeLines()
    window.addEventListener('resize', computeLines)
    return () => window.removeEventListener('resize', computeLines)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roadmap])

  const grouped = COLUMNS.map((col) => ({
    ...col,
    tasks: roadmap.filter((t) => t.status === col.id),
  }))

  const hoursRemaining = summary?.hours_remaining
  const percentComplete = summary ? Math.round(summary.percent_complete) : 0

  return (
    <div className="rounded-card border border-border bg-card p-5 shadow-card">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-text">Build deck</h2>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-muted">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-success" />
          live workflow · hover a node for details
        </div>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-4 sm:grid-cols-5">
        <Stat value={`${percentComplete}%`} label="Complete" />
        <Stat value={summary?.building_count ?? '—'} label="Building" />
        <Stat value={summary?.blocked_count ?? '—'} label="Blocked" accent="danger" />
        <Stat value={summary ? `${summary.shipped_count}/${summary.total_count}` : '—'} label="Shipped" />
        <Stat value={summary?.commit_count ?? '—'} label="Commits" />
      </div>

      <div className="mb-5 h-1.5 w-full overflow-hidden rounded-full bg-bg">
        <div
          className="h-full rounded-full bg-primary transition-all"
          style={{ width: `${Math.min(100, Math.max(0, percentComplete))}%` }}
        />
      </div>

      <div ref={containerRef} className="relative rounded-card bg-bg/60 p-4">
        <svg className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden="true">
          {lines.map((line, i) => (
            <path
              key={i}
              d={`M ${line.from.x} ${line.from.y} C ${(line.from.x + line.to.x) / 2} ${line.from.y}, ${(line.from.x + line.to.x) / 2} ${line.to.y}, ${line.to.x} ${line.to.y}`}
              fill="none"
              stroke={line.color}
              strokeWidth={1.5}
              strokeDasharray="4 4"
              opacity={0.6}
            />
          ))}
        </svg>

        <div className="relative grid grid-cols-1 gap-4 sm:grid-cols-4">
          {grouped.map((col) => (
            <div key={col.id} className="flex flex-col gap-2">
              <div className="flex items-center gap-2 px-1">
                <span className={cn('h-2 w-2 rounded-full', col.dot)} />
                <span className={cn('text-xs font-semibold uppercase tracking-wide', col.badgeText)}>
                  {col.label}
                </span>
                <span className="ml-auto text-xs text-muted">{col.tasks.length}</span>
              </div>

              <div className="flex flex-col gap-2">
                {col.tasks.map((task) => (
                  <div key={task.id} ref={registerCard(task.id)}>
                    <BuildDeckCard task={task} />
                  </div>
                ))}
                {col.tasks.length === 0 && (
                  <div className="rounded-card border border-dashed border-border-soft py-4 text-center text-xs text-muted">
                    Nothing here
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
        <div className="flex items-center gap-4">
          {COLUMNS.map((col) => (
            <span key={col.id} className="inline-flex items-center gap-1.5">
              <span className={cn('h-1.5 w-1.5 rounded-full', col.dot)} />
              {col.label}
            </span>
          ))}
        </div>
        <span>
          Monitoring loop{hoursRemaining != null ? ` · ${formatHours(hoursRemaining)} left` : ''}
        </span>
      </div>
    </div>
  )
}

function Stat({
  value,
  label,
  accent,
}: {
  value: string | number
  label: string
  accent?: 'danger'
}) {
  return (
    <div>
      <p className={cn('text-lg font-semibold', accent === 'danger' ? 'text-danger' : 'text-text')}>{value}</p>
      <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
    </div>
  )
}

const STATUS_DOT: Record<RoadmapTask['status'], string> = {
  todo: 'bg-muted-2',
  in_progress: 'bg-purple',
  blocked: 'bg-danger',
  done: 'bg-success',
}

function BuildDeckCard({ task }: { task: RoadmapTask }) {
  const isBlocked = task.status === 'blocked'
  const isDone = task.status === 'done'

  return (
    <div
      title={task.task}
      className={cn(
        'rounded-card border p-2.5 transition-colors',
        isBlocked ? 'border-danger/30 bg-danger-soft' : 'border-border bg-card hover:border-primary/40'
      )}
    >
      <div className="mb-1.5 flex items-center gap-1.5">
        <span className={cn('h-1.5 w-1.5 flex-shrink-0 rounded-full', STATUS_DOT[task.status])} />
        <p className="truncate text-xs font-medium text-text">{task.task}</p>
      </div>
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-1 rounded-full bg-navy-soft px-1.5 py-0.5 text-[10px] font-semibold text-navy">
          {task.owner.slice(0, 2).toUpperCase()}
          <span className="max-w-[6rem] truncate font-normal normal-case text-navy/80">{task.owner}</span>
        </span>
        <span className={cn('text-[11px]', isBlocked ? 'text-danger' : 'text-muted')}>
          {isDone ? 'done' : isBlocked ? 'blocked' : task.eta}
        </span>
      </div>
    </div>
  )
}
