import type { Risk } from '@/types'
import { cn, severityColor } from '@/lib/utils'

export function RiskPanel({ risks }: { risks: Risk[] }) {
  const open = risks.filter((r) => !r.resolved)

  if (open.length === 0) {
    return <p className="text-sm text-muted">No open risks.</p>
  }

  return (
    <div className="space-y-2">
      {open.map((risk) => (
        <div key={risk.id} className="rounded-lg border border-border bg-card p-3">
          <div className="flex items-center gap-2">
            <span className={cn('h-2 w-2 rounded-full', severityColor(risk.severity))} />
            <p className="text-sm font-medium text-text">{risk.risk}</p>
          </div>
          <p className="mt-1 pl-4 text-xs text-muted">{risk.suggested_fix}</p>
        </div>
      ))}
    </div>
  )
}
