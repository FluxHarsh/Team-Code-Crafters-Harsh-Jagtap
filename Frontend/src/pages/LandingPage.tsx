import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { projectsApi } from '@/api'

export function LandingPage() {
  const navigate = useNavigate()
  const [idea, setIdea] = useState('')

  const create = useMutation({
    mutationFn: () => projectsApi.create(idea),
    onSuccess: (res) => {
      navigate(`/projects/${res.project_id}/context`)
    },
  })

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-bg px-4">
      <div className="w-full max-w-lg">
        <div className="mb-6 flex items-center justify-center gap-2">
          <Sparkles className="h-6 w-6 text-primary" />
          <h1 className="text-2xl font-semibold text-text">Hackathon Coach</h1>
        </div>
        <p className="mb-6 text-center text-sm text-muted">
          Tell us your idea. We'll scope it, plan it, and keep you on track.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (idea.trim()) create.mutate()
          }}
          className="rounded-card border border-border bg-card p-4 shadow-card"
        >
          <textarea
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            placeholder="e.g. An AI copilot that helps hackathon teams stay on schedule…"
            rows={4}
            className="w-full resize-none rounded-lg border border-border p-3 text-sm outline-none focus:border-primary"
          />
          <button
            type="submit"
            disabled={create.isPending || !idea.trim()}
            className="mt-3 w-full rounded-lg bg-primary py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {create.isPending ? 'Starting…' : 'Start building'}
          </button>
        </form>
      </div>
    </div>
  )
}
