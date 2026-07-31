import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { personalChatApi } from '@/api'
import { useStore } from '@/store'
import { ChatThread } from '@/components/chat/ChatThread'
import { ChatInput } from '@/components/chat/ChatInput'
import { generateId } from '@/lib/utils'

export function PersonalChatPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const queryClient = useQueryClient()
  const personalMessages = useStore((s) => s.personalMessages)
  const appendPersonalMessage = useStore((s) => s.appendPersonalMessage)

  const { data } = useQuery({
    queryKey: ['personal-chat-history', projectId],
    queryFn: () => personalChatApi.history(projectId!),
    enabled: !!projectId,
  })

  useEffect(() => {
    if (data) data.messages.forEach((m) => appendPersonalMessage(m))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data])

  const send = useMutation({
    mutationFn: (content: string) => personalChatApi.send(projectId!, { message: content }),
    onMutate: (content) => {
      appendPersonalMessage({ id: generateId(), role: 'user', content, phase: 'personal' })
    },
    onSuccess: (res) => {
      if (res.reply) {
        appendPersonalMessage({
          id: generateId(),
          role: 'agent',
          content: res.reply,
          speaker_name: res.answered_by ?? undefined,
          phase: 'personal',
        })
      }
      queryClient.invalidateQueries({ queryKey: ['personal-chat-history', projectId] })
    },
  })

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-6 py-4">
        <h1 className="text-lg font-semibold text-text">Coach</h1>
        <p className="text-sm text-muted">Your private 1:1 thread — not visible to teammates.</p>
      </div>
      <ChatThread messages={personalMessages} />
      <ChatInput onSend={(content) => send.mutate(content)} disabled={send.isPending} />
    </div>
  )
}
