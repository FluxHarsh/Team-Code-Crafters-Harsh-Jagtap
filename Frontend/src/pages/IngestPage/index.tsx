import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ingestApi } from '@/api'
import { generateId } from '@/lib/utils'
import { ChatThread } from '@/components/chat/ChatThread'
import { ChatComposer } from '@/components/chat/ChatComposer'
import { DocumentDropzone } from '@/components/chat/DocumentDropzone'
import { Button, InlineError } from '@/components/ui'
import type { ChatMessage } from '@/types'

export function IngestPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [readyForPlanning, setReadyForPlanning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [speakerName, setSpeakerName] = useState(() => localStorage.getItem('speakerName') ?? '')
  const [showDropzone, setShowDropzone] = useState(false)

  // Load history on mount
  // Backend returns {messages: [{role, content}]} — no id/phase/created_at
  // so we normalize each to a full ChatMessage shape here
  useEffect(() => {
    if (!projectId) return
    ingestApi.getHistory(projectId).then((data) => {
      if (data.messages.length > 0) {
        setMessages(
          data.messages.map((m) => ({
            id: generateId(),
            phase: 'intake' as const,
            role: m.role as ChatMessage['role'],
            content: m.content,
            created_at: new Date().toISOString(),
          }))
        )
      } else {
        setMessages([{
          id: generateId(),
          phase: 'intake',
          role: 'agent',
          agent_node: 'intake',
          content: "Tell me about the problem you're solving and your idea for it. What does your solution do, and who is it for?",
          created_at: new Date().toISOString(),
        }])
      }
    }).catch(() => {
      setMessages([{
        id: generateId(),
        phase: 'intake',
        role: 'agent',
        agent_node: 'intake',
        content: "Tell me about the problem you're solving and your idea for it. What does your solution do, and who is it for?",
        created_at: new Date().toISOString(),
      }])
    })
  }, [projectId])

  const handleSend = async (text: string, name?: string) => {
    if (!projectId) return

    if (name) {
      setSpeakerName(name)
      localStorage.setItem('speakerName', name)
    }

    const userMsg: ChatMessage = {
      id: generateId(),
      phase: 'intake',
      role: 'user',
      content: text,
      speaker_name: name || speakerName || undefined,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)
    setError(null)

    try {
      const data = await ingestApi.sendMessage(projectId, text)
      const agentMsg: ChatMessage = {
        id: generateId(),
        phase: 'intake',
        role: 'agent',
        agent_node: 'intake',
        content: data.reply,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, agentMsg])
      if (data.ready_for_planning) setReadyForPlanning(true)
    } catch (e: any) {
      setError(e.message ?? 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  const handleUpload = async (file: File) => {
    if (!projectId) throw new Error('No project')
    const result = await ingestApi.uploadDocument(projectId, file)
    setMessages((prev) => [...prev, {
      id: generateId(),
      phase: 'intake',
      role: 'user',
      content: `📎 Uploaded "${result.filename}" (${(result.extracted_chars / 1000).toFixed(1)}k chars extracted)`,
      speaker_name: speakerName || undefined,
      created_at: new Date().toISOString(),
    }])
    return result
  }

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-border px-5 py-3 flex items-center gap-3 flex-none">
        <div className="w-7 h-7 rounded-[9px] bg-primary flex items-center justify-center font-800 text-white text-xs shadow-md shadow-primary/30">
          HC
        </div>
        <div className="flex-1">
          <p className="text-sm font-700 text-navy leading-none">Hackathon Coach</p>
          <p className="text-[10px] text-muted-2 mt-0.5">Intake — describe your project</p>
        </div>

        {/* Phase stepper */}
        <div className="hidden sm:flex items-center gap-1.5">
          {[
            { n: 1, label: 'Intake', active: true },
            { n: 2, label: 'Planning', active: false },
            { n: 3, label: 'Dashboard', active: false },
          ].map((s) => (
            <div key={s.n} className="flex items-center gap-1.5">
              <div className={`w-5 h-5 rounded-full text-[10px] font-800 flex items-center justify-center ${s.active ? 'bg-primary text-white' : 'bg-border text-muted-2'}`}>
                {s.n}
              </div>
              <span className={`text-[11px] font-600 ${s.active ? 'text-primary-dark' : 'text-muted-2'}`}>{s.label}</span>
              {s.n < 3 && <span className="text-muted-2 text-[10px]">›</span>}
            </div>
          ))}
        </div>
      </header>

      {/* Chat area */}
      <div className="flex-1 max-w-2xl w-full mx-auto flex flex-col">
        <ChatThread
          messages={messages}
          loading={loading}
          agentName="Intake Agent"
          className="flex-1 min-h-0"
        />

        {/* Ready for planning CTA */}
        {readyForPlanning && (
          <div className="mx-4 mb-3 p-3 bg-success-soft border border-green-200 rounded-[10px] flex items-center justify-between gap-3 animate-fadeUp">
            <div>
              <p className="text-xs font-700 text-success-dark">Ready to plan!</p>
              <p className="text-[11px] text-success-dark/70">The agent has enough context to build your roadmap.</p>
            </div>
            <Button
              onClick={() => navigate(`/projects/${projectId}/plan`)}
              size="sm"
              className="flex-none"
            >
              Continue to planning →
            </Button>
          </div>
        )}

        {error && <div className="px-4 pb-2"><InlineError message={error} /></div>}

        {showDropzone && (
          <div className="mx-4 mb-2 animate-fadeUp">
            <DocumentDropzone onUpload={handleUpload} />
          </div>
        )}

        <div className="border-t border-border bg-white">
          <div className="flex items-center gap-2 px-3 pt-2">
            <button
              onClick={() => setShowDropzone((v) => !v)}
              className={`text-xs font-600 px-2.5 py-1 rounded-[7px] transition ${showDropzone ? 'bg-primary-soft text-primary-dark' : 'text-muted hover:bg-bg'}`}
            >
              📎 Attach file
            </button>
          </div>
          <ChatComposer
            onSend={handleSend}
            disabled={loading}
            placeholder="Describe your problem, solution, or ask the agent a question…"
            showSpeakerName
            speakerName={speakerName}
            onSpeakerNameChange={(n) => { setSpeakerName(n); localStorage.setItem('speakerName', n) }}
          />
        </div>
      </div>
    </div>
  )
}