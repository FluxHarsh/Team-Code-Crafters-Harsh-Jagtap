import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { pitchApi } from '@/api'

export function PitchPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['pitch', projectId],
    queryFn: () => pitchApi.get(projectId!),
    enabled: !!projectId,
  })

  const generate = useMutation({
    mutationFn: () => pitchApi.generate(projectId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pitch', projectId] })
    },
  })

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="skeleton h-8 w-48" />
      </div>
    )
  }

  const outline = data?.pitch_outline

  return (
    <div className="mx-auto max-w-2xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-text">Pitch outline</h1>
        <button
          onClick={() => generate.mutate()}
          disabled={generate.isPending}
          className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-text hover:bg-bg disabled:opacity-50"
        >
          <RefreshCw className={generate.isPending ? 'h-3.5 w-3.5 animate-spin' : 'h-3.5 w-3.5'} />
          {generate.isPending ? 'Generating…' : 'Regenerate'}
        </button>
      </div>

      {!outline && <p className="text-sm text-muted">No pitch generated yet.</p>}

      {outline && (
        <div className="space-y-5 rounded-card border border-border bg-card p-5 shadow-card">
          {outline.hook && <Section label="Hook" value={outline.hook} />}
          <Section label="Problem" value={outline.problem} />
          <Section label="Solution" value={outline.solution} />
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">Demo flow</p>
            <ol className="list-decimal space-y-1 pl-4 text-sm text-text">
              {outline.demo_flow.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          </div>
          <Section label="Differentiator" value={outline.differentiator} />
          {outline.ask && <Section label="Ask" value={outline.ask} />}
        </div>
      )}
    </div>
  )
}

function Section({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <p className="text-sm text-text">{value}</p>
    </div>
  )
}
