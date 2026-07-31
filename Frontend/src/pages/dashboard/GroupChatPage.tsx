import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { groupChatApi } from '@/api'
import { useStore } from '@/store'
import { ChatThread } from '@/components/chat/ChatThread'
import { ChatInput } from '@/components/chat/ChatInput'
import { generateId } from '@/lib/utils'

export function GroupChatPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const queryClient = useQueryClient()
  const groupMessages = useStore((s) => s.groupMessages)
  const appendGroupMessage = useStore((s) => s.appendGroupMessage)
  // Lightweight speaker identity until real auth/session identity exists
  const [speakerName] = useState(() => localStorage.getItem('hc_speaker_name') || 'You')

  const { data } = useQuery({
    queryKey: ['group-chat-history', projectId],
    queryFn: () => groupChatApi.history(projectId!),
    enabled: !!projectId,
  })

  useEffect(() => {
    if (data) data.messages.forEach((m) => appendGroupMessage(m))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data])

  const send = useMutation({
    mutationFn: (content: string) => groupChatApi.send(projectId!, { message: content, speaker_name: speakerName }),
    onMutate: (content) => {
      appendGroupMessage({
        id: generateId(),
        role: 'user',
        content,
        speaker_name: speakerName,
        phase: 'group',
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['group-chat-history', projectId] })
    },
  })

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-6 py-4">
        <h1 className="text-lg font-semibold text-text">Group Chat</h1>
        <p className="text-sm text-muted">Shared with your whole team.</p>
      </div>
      <ChatThread messages={groupMessages} />
      <ChatInput onSend={(content) => send.mutate(content)} disabled={send.isPending} />
    </div>
  )
}
