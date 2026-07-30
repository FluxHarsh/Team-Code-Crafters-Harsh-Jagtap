import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { projectContextApi } from '@/api'
import { useStore } from '@/store'
import { ChatThread } from '@/components/chat/ChatThread'
import { ChatInput } from '@/components/chat/ChatInput'
import { DocumentDropzone } from '@/components/shared/DocumentDropzone'
import { generateId } from '@/lib/utils'

// Renamed from IngestPage: v2 replaces the deprecated /ingest/message,
// /ingest/document, /ingest/history trio with /context/message, /context/files,
// /context/history. Route path also moved from /ingest to /context.
export function ProjectContextPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const coachMessages = useStore((s) => s.coachMessages)
  const appendCoachMessage = useStore((s) => s.appendCoachMessage)

  const { data: history } = useQuery({
    queryKey: ['context-history', projectId],
    queryFn: () => projectContextApi.getHistory(projectId!),
    enabled: !!projectId,
  })

  useEffect(() => {
    if (history) history.messages.forEach((m) => appendCoachMessage(m))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history])

  const sendMessage = useMutation({
    mutationFn: (content: string) => projectContextApi.sendMessage(projectId!, content),
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
      queryClient.invalidateQueries({ queryKey: ['context-history', projectId] })
    },
  })

  const uploadFile = useMutation({
    mutationFn: (file: File) => projectContextApi.uploadFile(projectId!, file),
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
        <p className="text-sm text-muted">Chat with the coach or drop in any docs you already have.</p>
      </div>

      <ChatThread messages={coachMessages} />

      <div className="border-t border-border p-4">
        <DocumentDropzone onFileSelected={(file) => uploadFile.mutate(file)} disabled={uploadFile.isPending} />
      </div>

      <ChatInput
        onSend={(content) => sendMessage.mutate(content)}
        disabled={sendMessage.isPending}
        placeholder="Describe your idea…"
      />
    </div>
  )
}
