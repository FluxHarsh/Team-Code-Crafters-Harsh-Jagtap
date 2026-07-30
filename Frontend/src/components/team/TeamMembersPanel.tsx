import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { UserPlus, X } from 'lucide-react'
import { teamMembersApi } from '@/api'
import { useStore } from '@/store'
import { useEffect } from 'react'

export function TeamMembersPanel({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient()
  const setTeamMembers = useStore((s) => s.setTeamMembers)
  const teamMembers = useStore((s) => s.teamMembers)
  const [name, setName] = useState('')
  const [role, setRole] = useState('')

  const { data } = useQuery({
    queryKey: ['team-members', projectId],
    queryFn: () => teamMembersApi.list(projectId),
  })

  useEffect(() => {
    if (data) setTeamMembers(data.members)
  }, [data, setTeamMembers])

  const addMember = useMutation({
    mutationFn: () => teamMembersApi.add(projectId, { name, role: role || undefined }),
    onSuccess: (res) => {
      setTeamMembers(res.members)
      setName('')
      setRole('')
      queryClient.invalidateQueries({ queryKey: ['team-members', projectId] })
    },
  })

  const removeMember = useMutation({
    mutationFn: (memberId: string) => teamMembersApi.remove(projectId, memberId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['team-members', projectId] }),
  })

  return (
    <div className="mx-auto max-w-2xl p-8">
      <h1 className="mb-1 text-lg font-semibold text-text">Team</h1>
      <p className="mb-6 text-sm text-muted">Everyone with access to this project's coach.</p>

      <div className="space-y-2">
        {teamMembers.map((m) => (
          <div key={m.id} className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-purple-soft text-xs font-semibold text-purple">
              {m.avatar_initials}
            </span>
            <div className="flex-1">
              <p className="text-sm font-medium text-text">{m.name}</p>
              {m.role && <p className="text-xs text-muted">{m.role}</p>}
            </div>
            <button
              onClick={() => removeMember.mutate(m.id)}
              className="text-muted hover:text-danger"
              aria-label={`Remove ${m.name}`}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
        {teamMembers.length === 0 && <p className="text-sm text-muted">No team members yet.</p>}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (name.trim()) addMember.mutate()
        }}
        className="mt-6 flex gap-2"
      >
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Name"
          className="flex-1 rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
        />
        <input
          value={role}
          onChange={(e) => setRole(e.target.value)}
          placeholder="Role (optional)"
          className="w-40 rounded-lg border border-border px-3 py-2 text-sm outline-none focus:border-primary"
        />
        <button
          type="submit"
          disabled={addMember.isPending || !name.trim()}
          className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          <UserPlus className="h-4 w-4" />
          Add
        </button>
      </form>
    </div>
  )
}
