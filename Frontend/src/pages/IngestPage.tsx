import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ingestApi } from '@/api'
import { useStore } from '@/store'
import { ChatThread } from '@/components/chat/ChatThread'
import { ChatInput } from '@/components/chat/ChatInput'
import { generateId } from '@/lib/utils'

// Hits the real backend's /ingest/message, /ingest/document, /ingest/history
// trio directly (there is no /context/* surface on the backend).
export function IngestPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const coachMessages = useStore((s) => s.coachMessages)
  const appendCoachMessage = useStore((s) => s.appendCoachMessage)

  const { data: history } = useQuery({
    queryKey: ['ingest-history', projectId],
    queryFn: () => ingestApi.getHistory(projectId!),
    enabled: !!projectId,
  })

  useEffect(() => {
    if (history?.messages) {
      history.messages.forEach((m) => {
        const exists = coachMessages.some(
          (existing) =>
            existing.id === m.id ||
            (existing.content === m.content && existing.role === m.role)
        )
        if (!exists) {
          appendCoachMessage(m)
        }
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history])

  const sendMessage = useMutation({
    mutationFn: (content: string) => ingestApi.sendMessage(projectId!, content),
    onMutate: (content) => {
      appendCoachMessage({ id: generateId(), role: 'user', content, phase: 'project_context' })
    },
    onSuccess: (res) => {
      appendCoachMessage({
        id: generateId(),
        role: 'agent',
        content: res.reply,
        phase: 'project_context',
      })
      if (res.ready_for_planning) {
        navigate(`/projects/${projectId}/plan`)
      }
      queryClient.invalidateQueries({ queryKey: ['ingest-history', projectId] })
    },
  })

  const uploadDocument = useMutation({
    mutationFn: (file: File) => ingestApi.uploadDocument(projectId!, file),
    onSuccess: (res) => {
      appendCoachMessage({
        id: generateId(),
        role: 'agent',
        content: `Got it — read ${res.extracted_chars.toLocaleString()} characters from "${res.filename}".`,
        phase: 'project_context',
      })
    },
  })

  return (
    <div className="mx-auto flex h-screen max-w-2xl flex-col">
      <div className="border-b border-border px-6 py-4">
        <h1 className="text-lg font-semibold text-text">Tell us about your project</h1>
        <p className="text-sm text-muted">Chat with the coach or attach any docs you already have.</p>
      </div>

      <ChatThread messages={coachMessages} />

      <ChatInput
        onSend={(content) => sendMessage.mutate(content)}
        onFileSelected={(file) => uploadDocument.mutate(file)}
        isUploading={uploadDocument.isPending}
        disabled={sendMessage.isPending}
        placeholder="Describe your idea…"
      />
    </div>
  )
}

