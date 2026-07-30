import { useEffect, useRef } from 'react'
import { cn, formatTime } from '@/lib/utils'
import type { ChatMessage } from '@/types'

interface ChatBubbleProps {
  message: ChatMessage
}

export function ChatBubble({ message }: ChatBubbleProps) {
  const isUser = message.role === 'user'
  return (
    <div className={cn('flex gap-2.5 chat-bubble-enter', isUser && 'flex-row-reverse')}>
      {/* Avatar */}
      <div
        className={cn(
          'w-7 h-7 rounded-[8px] flex items-center justify-center text-xs font-700 flex-none mt-0.5',
          isUser
            ? 'bg-navy text-white'
            : 'bg-primary-soft text-primary-dark'
        )}
      >
        {isUser ? (message.speaker_name?.[0]?.toUpperCase() ?? 'U') : '⚡'}
      </div>

      <div className={cn('flex flex-col gap-1 max-w-[78%]', isUser && 'items-end')}>
        {/* Speaker label */}
        {message.speaker_name && isUser && (
          <span className="text-[10px] font-600 text-muted-2 px-1">
            {message.speaker_name}
          </span>
        )}
        {!isUser && message.agent_node && (
          <span className="text-[10px] font-600 text-primary-dark/70 px-1">
            {message.agent_node.replace(/_/g, ' ')}
          </span>
        )}

        {/* Bubble */}
        <div
          className={cn(
            'px-3.5 py-2.5 rounded-[12px] text-sm leading-relaxed',
            isUser
              ? 'bg-navy text-white rounded-tr-[4px]'
              : 'bg-white border border-border text-text rounded-tl-[4px] shadow-sm'
          )}
        >
          {message.content}
        </div>

        {/* Timestamp */}
        <span className="text-[10px] text-muted-2 px-1 font-mono">
          {formatTime(message.created_at)}
        </span>
      </div>
    </div>
  )
}

interface TypingIndicatorProps { agentName?: string }
export function TypingIndicator({ agentName }: TypingIndicatorProps) {
  return (
    <div className="flex gap-2.5 chat-bubble-enter">
      <div className="w-7 h-7 rounded-[8px] bg-primary-soft text-primary-dark flex items-center justify-center text-xs font-700 flex-none">
        ⚡
      </div>
      <div className="flex flex-col gap-1">
        {agentName && (
          <span className="text-[10px] font-600 text-primary-dark/70 px-1">{agentName}</span>
        )}
        <div className="bg-white border border-border rounded-[12px] rounded-tl-[4px] px-4 py-3 shadow-sm">
          <span className="flex gap-1">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="w-1.5 h-1.5 rounded-full bg-muted-2 animate-bounce"
                style={{ animationDelay: `${i * 0.15}s` }}
              />
            ))}
          </span>
        </div>
      </div>
    </div>
  )
}

interface ChatThreadProps {
  messages: ChatMessage[]
  loading?: boolean
  agentName?: string
  className?: string
}

export function ChatThread({ messages, loading, agentName, className }: ChatThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  return (
    <div className={cn('flex flex-col gap-4 overflow-y-auto p-4', className)}>
      {messages.map((m) => (
        <ChatBubble key={m.id} message={m} />
      ))}
      {loading && <TypingIndicator agentName={agentName} />}
      <div ref={bottomRef} />
    </div>
  )
}
