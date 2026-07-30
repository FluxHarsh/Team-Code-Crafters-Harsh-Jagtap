import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { projectsApi } from '@/api'
import { Button, Input, InlineError } from '@/components/ui'

export function LandingPage() {
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const handleStart = async () => {
    const trimmed = name.trim()
    if (!trimmed) return
    setLoading(true)
    setError(null)
    try {
      const data = await projectsApi.create(trimmed)
      navigate(`/projects/${data.project_id}/ingest`)
    } catch (e: any) {
      setError(e.message ?? 'Failed to create project')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Brand mark */}
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-[12px] bg-primary flex items-center justify-center font-800 text-white text-sm shadow-lg shadow-primary/30">
            HC
          </div>
          <div>
            <p className="text-lg font-800 text-navy leading-none">Hackathon Coach</p>
            <p className="text-xs text-muted-2 mt-0.5">AI-powered team navigator</p>
          </div>
        </div>

        {/* Card */}
        <div className="bg-white border border-border rounded-card shadow-card p-6">
          <h1 className="text-xl font-800 text-navy mb-1">Start a new project</h1>
          <p className="text-sm text-muted mb-5">
            Your coach will help you scope, plan, and build — and keep watch for 24 hours, even while you're away from the table.
          </p>

          <div className="space-y-4">
            <Input
              id="name"
              label="Project name"
              placeholder="e.g. HackPilot AI"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleStart()}
              autoFocus
            />

            <InlineError message={error} />

            <Button
              onClick={handleStart}
              loading={loading}
              disabled={!name.trim()}
              size="lg"
              className="w-full"
            >
              Start coaching →
            </Button>
          </div>
        </div>

        {/* How it works */}
        <div className="mt-6 grid grid-cols-3 gap-3">
          {[
            { step: '1', label: 'Intake', desc: 'Describe your idea via chat' },
            { step: '2', label: 'Plan', desc: 'Planner builds your roadmap' },
            { step: '3', label: 'Monitor', desc: 'Coach watches GitHub 24/7' },
          ].map((s) => (
            <div key={s.step} className="bg-white border border-border rounded-[10px] p-3 text-center">
              <div className="w-6 h-6 rounded-full bg-primary-soft text-primary-dark text-xs font-800 flex items-center justify-center mx-auto mb-1.5">
                {s.step}
              </div>
              <p className="text-[11px] font-700 text-navy">{s.label}</p>
              <p className="text-[10px] text-muted-2 mt-0.5">{s.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
