import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { projectsApi } from '@/api'

export function LandingPage() {
  const navigate = useNavigate()
  const [name, setName] = useState('')

  const create = useMutation({
    mutationFn: () => projectsApi.create(name),
    onSuccess: (res) => {
      navigate(`/projects/${res.project_id}/ingest`)
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
          Give your project a name. We'll scope it, plan it, and keep you on track.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (name.trim()) create.mutate()
          }}
          className="rounded-card border border-border bg-card p-4 shadow-card"
        >
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. HackPilot AI"
            className="w-full rounded-lg border border-border p-3 text-sm outline-none focus:border-primary"
          />
          <button
            type="submit"
            disabled={create.isPending || !name.trim()}
            className="mt-3 w-full rounded-lg bg-primary py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {create.isPending ? 'Starting…' : 'Start building'}
          </button>
        </form>
      </div>
    </div>
  )
}
