import { cn } from '@/lib/utils'
import { Button } from '@/components/ui'
import type { ScopeData, RoadmapTask } from '@/types'

// ─── DraftPlanPanel ───────────────────────────────────────────────────────────

interface DraftPlanPanelProps {
  scope?: ScopeData
  roadmap?: RoadmapTask[]
}

export function DraftPlanPanel({ scope, roadmap }: DraftPlanPanelProps) {
  if (!scope && !roadmap) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center px-4 py-8">
        <p className="text-2xl mb-2">🗺️</p>
        <p className="text-xs font-600 text-muted">Plan will appear here</p>
        <p className="text-[11px] text-muted-2 mt-1">
          Keep chatting with the Planner — scope and roadmap update as you go
        </p>
      </div>
    )
  }

  return (
    <div className="overflow-y-auto h-full p-4 space-y-4">
      {/* Scope */}
      {scope && (
        <div className="space-y-2.5">
          <p className="text-[10px] font-700 uppercase tracking-wider text-muted-2">MVP Scope</p>

          {scope.mvp_features.length > 0 && (
            <div>
              <p className="text-[10px] font-600 text-success-dark mb-1.5">✓ Building</p>
              <div className="flex flex-wrap gap-1.5">
                {scope.mvp_features.map((f, i) => (
                  <span key={i} className="text-[11px] font-600 bg-success-soft border border-green-200 text-success-dark px-2 py-0.5 rounded-[6px]">
                    {f}
                  </span>
                ))}
              </div>
            </div>
          )}

          {scope.cut_features.length > 0 && (
            <div>
              <p className="text-[10px] font-600 text-muted-2 mb-1.5">✕ Cut from MVP</p>
              <div className="flex flex-wrap gap-1.5">
                {scope.cut_features.map((f, i) => (
                  <span key={i} className="text-[11px] font-600 bg-border text-muted-2 px-2 py-0.5 rounded-[6px] line-through">
                    {f}
                  </span>
                ))}
              </div>
            </div>
          )}

          {scope.assumptions.length > 0 && (
            <div>
              <p className="text-[10px] font-600 text-gold mb-1.5">~ Assumptions</p>
              <ul className="space-y-1">
                {scope.assumptions.map((a, i) => (
                  <li key={i} className="text-[11px] text-muted flex gap-1.5">
                    <span className="text-muted-2">•</span>{a}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Roadmap */}
      {roadmap && roadmap.length > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] font-700 uppercase tracking-wider text-muted-2">Draft Roadmap</p>
          <div className="space-y-1.5">
            {roadmap.map((task, i) => (
              <div key={task.id ?? i} className="flex items-start gap-2 bg-white border border-border rounded-[8px] p-2.5">
                <span className="text-[10px] font-800 text-muted-2 w-4 flex-none mt-0.5">{i + 1}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-[11px] font-600 text-navy leading-snug">{task.task}</p>
                  <div className="flex items-center gap-2 mt-1">
                    {task.owner && (
                      <span className="text-[10px] text-muted-2">👤 {task.owner}</span>
                    )}
                    {task.eta && (
                      <span className="text-[10px] text-muted-2 font-mono">📅 {task.eta}</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── ApprovalBar ──────────────────────────────────────────────────────────────

interface ApprovalBarProps {
  onApprove: () => void
  loading: boolean
  error: string | null
  disabled: boolean
}

export function ApprovalBar({ onApprove, loading, error, disabled }: ApprovalBarProps) {
  return (
    <div className="border-t border-border bg-white px-4 py-3">
      {error && (
        <div className="mb-2 text-xs text-danger bg-danger-soft border border-red-200 rounded-[7px] px-3 py-2">
          {error}
        </div>
      )}
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-700 text-navy">Happy with the plan?</p>
          <p className="text-[11px] text-muted-2">Approving unlocks the live dashboard and starts monitoring.</p>
        </div>
        <Button
          onClick={onApprove}
          loading={loading}
          disabled={disabled}
          size="md"
          className="flex-none"
        >
          Approve & open dashboard →
        </Button>
      </div>
    </div>
  )
}
