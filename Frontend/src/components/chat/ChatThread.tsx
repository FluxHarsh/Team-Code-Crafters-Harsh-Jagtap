import { useEffect, useRef } from 'react'
import type { ChatMessage } from '@/types'
import { cn, formatTime } from '@/lib/utils'

export function ChatThread({ messages }: { messages: ChatMessage[] }) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  return (
    <div className="flex-1 space-y-3 overflow-y-auto p-6">
      {messages.map((msg, i) => (
        <div
          key={msg.id ?? `${msg.role}-${i}`}
          className={cn('chat-bubble-enter flex flex-col', msg.role === 'user' ? 'items-end' : 'items-start')}
        >
          {msg.speaker_name && msg.role === 'user' && (
            <span className="mb-1 px-1 text-[11px] text-muted">{msg.speaker_name}</span>
          )}
          <div
            className={cn(
              'max-w-[75%] rounded-2xl px-4 py-2 text-sm',
              msg.role === 'user' ? 'bg-primary text-white' : 'bg-card border border-border text-text'
            )}
          >
            {msg.content}
          </div>
          {msg.created_at && (
            <span className="mt-1 px-1 text-[10px] text-muted-2">{formatTime(msg.created_at)}</span>
          )}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
