import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { useStore } from '@/store'
import { chatApi } from '@/api'
import { generateId, formatTime } from '@/lib/utils'
import { ChatThread } from './ChatThread'
import { ChatComposer } from './ChatComposer'
import type { ChatMessage } from '@/types'

interface CoachChatPanelProps {
  projectId: string
}

export function CoachChatPanel({ projectId }: CoachChatPanelProps) {
  const { chatPanelOpen, setChatPanelOpen, coachMessages, appendCoachMessage, setCoachMessages } =
    useStore()

  const [loading, setLoading] = useState(false)
  const [speakerName, setSpeakerName] = useState(() => localStorage.getItem('speakerName') ?? '')
  const [initialized, setInitialized] = useState(false)

  // Load history on first open
  // Backend GET /chat/history returns {id, role, content, agent_node, speaker_name, created_at}
  // — no "phase" field, so we inject it client-side
  useEffect(() => {
    if (!chatPanelOpen || initialized) return
    setInitialized(true)
    chatApi.getHistory(projectId).then((data) => {
      setCoachMessages(
        data.messages.map((m) => ({
          ...m,
          phase: 'coaching' as const,
        }))
      )
    }).catch(() => {})
  }, [chatPanelOpen, initialized, projectId, setCoachMessages])

  const handleSpeakerNameChange = (name: string) => {
    setSpeakerName(name)
    localStorage.setItem('speakerName', name)
  }

  const handleSend = async (text: string) => {
    const isAiMention = text.includes('@AI') || text.includes('@ai')

    const userMsg: ChatMessage = {
      id: generateId(),
      phase: 'coaching',
      role: 'user',
      content: text,
      speaker_name: speakerName || undefined,
      created_at: new Date().toISOString(),
    }
    appendCoachMessage(userMsg)

    if (!isAiMention) {
      return
    }

    setLoading(true)
    try {
      const cleanMsg = text.replace(/@AI|@ai/g, '').trim()
      const data = await chatApi.send(projectId, cleanMsg || text)
      const agentMsg: ChatMessage = {
        id: generateId(),
        phase: 'coaching',
        role: 'agent',
        content: data.reply,
        agent_node: data.answered_by,
        created_at: new Date().toISOString(),
      }
      appendCoachMessage(agentMsg)
    } catch {
      appendCoachMessage({
        id: generateId(),
        phase: 'coaching',
        role: 'agent',
        content: 'Something went wrong. Please try again.',
        created_at: new Date().toISOString(),
      })
    } finally {
      setLoading(false)
    }
  }

  if (!chatPanelOpen) return null

  return (
    <>
      <div
        className="fixed inset-0 bg-black/20 z-30 lg:hidden"
        onClick={() => setChatPanelOpen(false)}
      />

      <div className="fixed right-0 top-0 h-full w-[360px] max-w-full bg-white border-l border-border shadow-2xl z-40 flex flex-col animate-slideIn">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div>
            <p className="text-sm font-700 text-navy">Coach Chat</p>
            <p className="text-[11px] text-muted-2">
              Use <span className="font-mono text-primary-dark font-600">@AI</span> to ask the coach · or leave a team note
            </p>
          </div>
          <button
            onClick={() => setChatPanelOpen(false)}
            className="w-7 h-7 flex items-center justify-center rounded-[7px] hover:bg-bg text-muted transition"
          >
            <X size={15} />
          </button>
        </div>

        {/* Messages */}
        <ChatThread
          messages={coachMessages}
          loading={loading}
          agentName="Coach AI"
          className="flex-1 min-h-0"
        />

        {coachMessages.length === 0 && !loading && (
          <div className="absolute inset-0 top-14 flex flex-col items-center justify-center text-center px-6 pointer-events-none">
            <div className="text-3xl mb-3">⚡</div>
            <p className="text-sm font-600 text-muted">Ask the coach anything</p>
            <p className="text-xs text-muted-2 mt-1">
              Try: "Why is this risk flagged?" or "re-plan the roadmap" or "@AI what should we cut?"
            </p>
          </div>
        )}

        <ChatComposer
          onSend={handleSend}
          disabled={loading}
          placeholder="@AI re-plan · or leave a team note…"
          showSpeakerName
          speakerName={speakerName}
          onSpeakerNameChange={handleSpeakerNameChange}
        />
      </div>
    </>
  )
}