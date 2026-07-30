import { useState, useRef, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui'

interface ChatComposerProps {
  onSend: (message: string, speakerName?: string) => void
  disabled?: boolean
  placeholder?: string
  showSpeakerName?: boolean
  speakerName?: string
  onSpeakerNameChange?: (name: string) => void
  className?: string
}

export function ChatComposer({
  onSend,
  disabled,
  placeholder = 'Type a message…',
  showSpeakerName,
  speakerName = '',
  onSpeakerNameChange,
  className,
}: ChatComposerProps) {
  const [text, setText] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
  }, [text])

  const hasAtAI = text.includes('@AI') || text.includes('@ai')

  const handleSend = () => {
    const trimmed = text.trim()
    if (!trimmed || disabled) return
    onSend(trimmed, speakerName || undefined)
    setText('')
    textareaRef.current?.focus()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className={cn('border-t border-border bg-white p-3', className)}>
      {showSpeakerName && (
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs text-muted-2 font-600">Your name</span>
          <input
            type="text"
            value={speakerName}
            onChange={(e) => onSpeakerNameChange?.(e.target.value)}
            placeholder="e.g. Dev A"
            className="text-xs border border-border rounded-[7px] px-2 py-1 bg-bg text-text placeholder:text-muted-2 outline-none focus:border-primary w-24"
          />
          <span className="text-[10px] text-muted-2 ml-auto">
            Type <span className="font-mono font-600 text-primary-dark">@AI</span> to route to the coach
          </span>
        </div>
      )}

      <div className="flex items-end gap-2">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            rows={1}
            className={cn(
              'w-full resize-none bg-bg border border-border rounded-[10px] px-3 py-2.5 text-sm text-text placeholder:text-muted-2 outline-none transition focus:border-primary focus:ring-1 focus:ring-primary/20 leading-relaxed',
              disabled && 'opacity-50 cursor-not-allowed'
            )}
          />
          {hasAtAI && (
            <div className="absolute bottom-full left-0 mb-1 flex items-center gap-1.5 bg-primary-soft border border-orange-200 text-primary-dark text-xs font-600 px-2.5 py-1 rounded-[7px]">
              <span>⚡</span> Routing to Coach AI
            </div>
          )}
        </div>
        <Button
          onClick={handleSend}
          disabled={!text.trim() || disabled}
          size="md"
          className="flex-none h-9 px-4"
        >
          Send
        </Button>
      </div>
      <p className="text-[10px] text-muted-2 mt-1.5 pl-0.5">
        Press <kbd className="font-mono bg-border px-1 rounded">Enter</kbd> to send,{' '}
        <kbd className="font-mono bg-border px-1 rounded">Shift+Enter</kbd> for new line
      </p>
    </div>
  )
}
