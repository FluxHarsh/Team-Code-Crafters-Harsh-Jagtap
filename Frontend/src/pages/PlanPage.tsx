import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { plannerApi } from '@/api'
import { PlanView } from '@/components/plan/PlanView'
import type { ScopeData, RoadmapTask } from '@/types'

// Rebuilt: v2's planner is iterative and versioned (draft → feedback →
// approve) instead of the old single-shot /plan/chat endpoint.
export function PlanPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [feedback, setFeedback] = useState('')
  const [current, setCurrent] = useState<{
    version: number
    scope: ScopeData
    roadmap: RoadmapTask[]
  } | null>(null)

  const { data: draft, isLoading } = useQuery({
    queryKey: ['plan-draft', projectId],
    queryFn: () => plannerApi.draft(projectId!),
    enabled: !!projectId,
  })

  useEffect(() => {
    if (draft) {
      setCurrent({ version: draft.version, scope: draft.draft_scope, roadmap: draft.draft_roadmap })
    }
  }, [draft])

  const sendFeedback = useMutation({
    mutationFn: () => plannerApi.feedback(projectId!, { feedback }),
    onSuccess: (res) => {
      setCurrent({ version: res.version, scope: res.draft_scope, roadmap: res.draft_roadmap })
      setFeedback('')
      queryClient.invalidateQueries({ queryKey: ['planner-history', projectId] })
    },
  })

  const approve = useMutation({
    mutationFn: () => plannerApi.approve(projectId!),
    onSuccess: () => {
      navigate(`/projects/${projectId}/dashboard`)
    },
  })

  if (isLoading || !current) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg">
        <div className="skeleton h-8 w-48" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-text">Plan — v{current.version}</h1>
          <p className="text-sm text-muted">Give feedback to refine, or approve when it looks right.</p>
        </div>
        <button
          onClick={() => approve.mutate()}
          disabled={approve.isPending}
          className="rounded-lg bg-success px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {approve.isPending ? 'Approving…' : 'Approve plan'}
        </button>
      </div>

      <div className="rounded-card border border-border bg-card p-5 shadow-card">
        <PlanView scope={current.scope} roadmap={current.roadmap} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (feedback.trim()) sendFeedback.mutate()
        }}
        className="mt-6 flex gap-2"
      >
        <input
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="e.g. Cut the notifications feature, add more buffer to day 2…"
          className="flex-1 rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
        />
        <button
          type="submit"
          disabled={sendFeedback.isPending || !feedback.trim()}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {sendFeedback.isPending ? 'Revising…' : 'Send feedback'}
        </button>
      </form>
    </div>
  )
}
