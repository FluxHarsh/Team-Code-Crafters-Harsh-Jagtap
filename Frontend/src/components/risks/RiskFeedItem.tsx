import { useState } from 'react'
import { cn } from '@/lib/utils'
import { Button, SeverityDot } from '@/components/ui'
import type { Risk } from '@/types'

interface RiskFeedItemProps {
  risk: Risk
  onResolve: (riskId: string, note: string) => Promise<void>
  onReprioritize?: (riskId: string) => Promise<void>
}

export function RiskFeedItem({ risk, onResolve, onReprioritize }: RiskFeedItemProps) {
  const [expanded, setExpanded] = useState(false)
  const [resolving, setResolving] = useState(false)
  const [reprioritizing, setReprioritizing] = useState(false)
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleResolve = async () => {
    setResolving(true)
    setError(null)
    try {
      await onResolve(risk.id, note || 'Resolved manually')
    } catch {
      setError('Failed to resolve — try again')
    } finally {
      setResolving(false)
    }
  }

  const handleReprioritize = async () => {
    if (!onReprioritize) return
    setReprioritizing(true)
    setError(null)
    try {
      await onReprioritize(risk.id)
    } catch {
      setError('Failed to reprioritize — try again')
    } finally {
      setReprioritizing(false)
    }
  }

  return (
    <div
      className={cn(
        'border rounded-[10px] p-3 transition-all',
        risk.resolved
          ? 'bg-success-soft/40 border-green-200 opacity-70'
          : risk.severity === 'high'
          ? 'bg-danger-soft border-red-200'
          : risk.severity === 'med'
          ? 'bg-gold-soft border-yellow-200'
          : 'bg-white border-border'
      )}
    >
      <div className="flex items-start gap-2.5">
        <SeverityDot severity={risk.severity} />

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <p className={cn('text-xs font-600 leading-snug', risk.resolved && 'line-through text-muted')}>
              {risk.resolved && <span className="text-success-dark mr-1 no-underline">✓</span>}
              {risk.risk}
            </p>
            <span
              className={cn(
                'text-[9.5px] font-700 uppercase px-1.5 py-0.5 rounded-[5px] flex-none',
                risk.severity === 'high' && 'bg-danger text-white',
                risk.severity === 'med' && 'bg-gold text-white',
                risk.severity === 'low' && 'bg-success text-white'
              )}
            >
              {risk.severity}
            </span>
          </div>

          {!risk.resolved && (
            <>
              <p className="text-[11px] text-muted mt-1 leading-relaxed">
                💡 {risk.suggested_fix}
              </p>

              {/* Actions */}
              <div className="flex items-center gap-2 mt-2.5">
                <button
                  onClick={() => setExpanded((v) => !v)}
                  className="text-[11px] font-600 text-primary hover:text-primary-dark transition"
                >
                  {expanded ? 'Cancel' : 'Resolve'}
                </button>
                {onReprioritize && (
                  <button
                    onClick={handleReprioritize}
                    disabled={reprioritizing}
                    className="text-[11px] font-600 text-purple hover:text-purple/80 transition disabled:opacity-50"
                  >
                    {reprioritizing ? 'Fixing…' : 'Auto-fix'}
                  </button>
                )}
              </div>

              {expanded && (
                <div className="mt-2 space-y-2 animate-fadeUp">
                  <input
                    type="text"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="Resolution note (optional)"
                    className="w-full text-xs border border-border rounded-[7px] px-2.5 py-1.5 bg-white outline-none focus:border-primary"
                  />
                  <Button
                    size="sm"
                    onClick={handleResolve}
                    loading={resolving}
                    className="w-full"
                  >
                    Mark resolved
                  </Button>
                  {error && <p className="text-[11px] text-danger">{error}</p>}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
