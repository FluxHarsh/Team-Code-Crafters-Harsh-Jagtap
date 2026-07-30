import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, X, Lightbulb } from 'lucide-react'
import { plannerSuggestionsApi } from '@/api'
import { useStore } from '@/store'
import { formatRelative } from '@/lib/utils'

export function PlannerSuggestionsInbox({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient()
  const suggestions = useStore((s) => s.plannerSuggestions)
  const setPlannerSuggestions = useStore((s) => s.setPlannerSuggestions)
  const markAccepted = useStore((s) => s.markPlannerSuggestionAccepted)
  const patchProject = useStore((s) => s.patchProject)

  const { data } = useQuery({
    queryKey: ['planner-suggestions', projectId],
    queryFn: () => plannerSuggestionsApi.list(projectId),
  })

  useEffect(() => {
    if (data) setPlannerSuggestions(data.suggestions)
  }, [data, setPlannerSuggestions])

  const accept = useMutation({
    mutationFn: (suggestionId: string) => plannerSuggestionsApi.accept(projectId, suggestionId),
    onSuccess: (res, suggestionId) => {
      markAccepted(suggestionId)
      patchProject({ roadmap: res.updated_roadmap })
      queryClient.invalidateQueries({ queryKey: ['project', projectId] })
    },
  })

  const dismiss = useMutation({
    mutationFn: (suggestionId: string) => plannerSuggestionsApi.dismiss(projectId, suggestionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['planner-suggestions', projectId] }),
  })

  const pending = suggestions.filter((s) => s.status === 'pending')

  return (
    <div className="mx-auto max-w-2xl p-8">
      <h1 className="mb-1 text-lg font-semibold text-text">Suggestions</h1>
      <p className="mb-6 text-sm text-muted">
        The Risk Watcher proposes fixes here instead of auto-replanning — review and accept each one.
      </p>

      <div className="space-y-3">
        {pending.map((s) => (
          <div key={s.id} className="rounded-card border border-border bg-card p-4">
            <div className="flex items-start gap-2">
              <Lightbulb className="mt-0.5 h-4 w-4 flex-shrink-0 text-gold" />
              <div className="flex-1">
                <p className="text-sm font-medium text-text">{s.title}</p>
                <p className="mt-1 text-xs text-muted">{s.rationale}</p>
                {s.diff_summary && (
                  <p className="mt-1 font-mono text-[11px] text-muted-2">{s.diff_summary}</p>
                )}
                <p className="mt-2 text-[11px] text-muted-2">{formatRelative(s.created_at)}</p>
              </div>
            </div>
            <div className="mt-3 flex justify-end gap-2">
              <button
                onClick={() => dismiss.mutate(s.id)}
                disabled={dismiss.isPending}
                className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs text-muted hover:bg-bg"
              >
                <X className="h-3.5 w-3.5" />
                Dismiss
              </button>
              <button
                onClick={() => accept.mutate(s.id)}
                disabled={accept.isPending}
                className="flex items-center gap-1 rounded-lg bg-success px-3 py-1.5 text-xs font-medium text-white"
              >
                <Check className="h-3.5 w-3.5" />
                Accept
              </button>
            </div>
          </div>
        ))}
        {pending.length === 0 && <p className="text-sm text-muted">No open suggestions right now.</p>}
      </div>
    </div>
  )
}
