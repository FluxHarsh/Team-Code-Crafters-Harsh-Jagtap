import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { planApi } from '@/api'
import { useProjectSocket } from '@/hooks/useProjectSocket'
import { generateId } from '@/lib/utils'
import { ChatThread } from '@/components/chat/ChatThread'
import { ChatComposer } from '@/components/chat/ChatComposer'
import { DraftPlanPanel, ApprovalBar } from '@/components/plan/DraftPlanPanel'
import { InlineError } from '@/components/ui'
import type { ChatMessage, ScopeData, RoadmapTask } from '@/types'

export function PlanPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [approving, setApproving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [approveError, setApproveError] = useState<string | null>(null)
  const [draftScope, setDraftScope] = useState<ScopeData | undefined>()
  const [draftRoadmap, setDraftRoadmap] = useState<RoadmapTask[] | undefined>()
  const [speakerName, setSpeakerName] = useState(() => localStorage.getItem('speakerName') ?? '')

  // WebSocket for plan_draft_updated / plan_approved
  useProjectSocket(projectId)

  // Load existing draft on mount
  useEffect(() => {
    if (!projectId) return
    planApi.getDraft(projectId).then((data) => {
      if (data.draft_scope) setDraftScope(data.draft_scope)
      if (data.draft_roadmap) setDraftRoadmap(data.draft_roadmap)
    }).catch(() => {})
  }, [projectId])

  // Opening greeting
  useEffect(() => {
    setMessages([{
      id: generateId(),
      phase: 'planning',
      role: 'agent',
      agent_node: 'planner',
      content: "I've reviewed your project idea. Let me propose a scope and roadmap — push back on anything, and I'll adjust. What should we prioritise?",
      created_at: new Date().toISOString(),
    }])
  }, [])

  const handleSend = async (text: string, name?: string) => {
    if (!projectId) return
    if (name) {
      setSpeakerName(name)
      localStorage.setItem('speakerName', name)
    }

    setMessages((prev) => [...prev, {
      id: generateId(),
      phase: 'planning',
      role: 'user',
      content: text,
      speaker_name: name || speakerName || undefined,
      created_at: new Date().toISOString(),
    }])
    setLoading(true)
    setError(null)

    try {
      const data = await planApi.chat(projectId, text)
      setMessages((prev) => [...prev, {
        id: generateId(),
        phase: 'planning',
        role: 'agent',
        agent_node: 'planner',
        content: data.reply,
        created_at: new Date().toISOString(),
      }])
      if (data.draft_scope) setDraftScope(data.draft_scope)
      if (data.draft_roadmap) setDraftRoadmap(data.draft_roadmap)
    } catch (e: any) {
      setError(e.message ?? 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async () => {
    if (!projectId) return
    setApproving(true)
    setApproveError(null)
    try {
      await planApi.approve(projectId)
      navigate(`/projects/${projectId}/dashboard`)
    } catch (e: any) {
      if (e.status === 409) {
        setApproveError('Plan not ready yet — keep chatting until the planner has a full roadmap.')
      } else {
        setApproveError(e.message ?? 'Approval failed')
      }
    } finally {
      setApproving(false)
    }
  }

  const hasPlan = !!(draftScope || draftRoadmap)

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-border px-5 py-3 flex items-center gap-3 flex-none">
        <div className="w-7 h-7 rounded-[9px] bg-primary flex items-center justify-center font-800 text-white text-xs shadow-md shadow-primary/30">
          HC
        </div>
        <div className="flex-1">
          <p className="text-sm font-700 text-navy leading-none">Hackathon Coach</p>
          <p className="text-[10px] text-muted-2 mt-0.5">Planning — shape your roadmap</p>
        </div>

        {/* Phase stepper */}
        <div className="hidden sm:flex items-center gap-1.5">
          {[
            { n: 1, label: 'Intake', done: true, active: false },
            { n: 2, label: 'Planning', done: false, active: true },
            { n: 3, label: 'Dashboard', done: false, active: false },
          ].map((s) => (
            <div key={s.n} className="flex items-center gap-1.5">
              <div className={`w-5 h-5 rounded-full text-[10px] font-800 flex items-center justify-center ${s.done ? 'bg-success text-white' : s.active ? 'bg-primary text-white' : 'bg-border text-muted-2'}`}>
                {s.done ? '✓' : s.n}
              </div>
              <span className={`text-[11px] font-600 ${s.active ? 'text-primary-dark' : s.done ? 'text-success-dark' : 'text-muted-2'}`}>{s.label}</span>
              {s.n < 3 && <span className="text-muted-2 text-[10px]">›</span>}
            </div>
          ))}
        </div>
      </header>

      {/* Split layout: chat left, draft plan right */}
      <div className="flex-1 flex overflow-hidden max-w-5xl mx-auto w-full">
        {/* Chat column */}
        <div className="flex-1 flex flex-col min-w-0 border-r border-border">
          <ChatThread
            messages={messages}
            loading={loading}
            agentName="Planner"
            className="flex-1 min-h-0"
          />
          {error && <div className="px-4 pb-2"><InlineError message={error} /></div>}
          <ChatComposer
            onSend={handleSend}
            disabled={loading}
            placeholder='"Cut the Neo4j panel" · "Add more time to auth" · push back on anything…'
            showSpeakerName
            speakerName={speakerName}
            onSpeakerNameChange={(n) => { setSpeakerName(n); localStorage.setItem('speakerName', n) }}
          />
        </div>

        {/* Draft plan column */}
        <div className="w-[320px] flex-none flex flex-col bg-white">
          <div className="px-4 py-3 border-b border-border-soft">
            <p className="text-xs font-700 text-navy">Draft Plan</p>
            <p className="text-[10px] text-muted-2 mt-0.5">Updates live as you chat</p>
          </div>
          <div className="flex-1 overflow-y-auto">
            <DraftPlanPanel scope={draftScope} roadmap={draftRoadmap} />
          </div>
          <ApprovalBar
            onApprove={handleApprove}
            loading={approving}
            error={approveError}
            disabled={!hasPlan}
          />
        </div>
      </div>
    </div>
  )
}
