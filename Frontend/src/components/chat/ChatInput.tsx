import { useState } from 'react'
import { Send } from 'lucide-react'

interface ChatInputProps {
  onSend: (content: string) => void
  disabled?: boolean
  placeholder?: string
}

export function ChatInput({ onSend, disabled, placeholder }: ChatInputProps) {
  const [value, setValue] = useState('')

  function submit() {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
  }

  return (
    <div className="flex items-center gap-2 border-t border-border bg-card p-4">
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            submit()
          }
        }}
        placeholder={placeholder ?? 'Type a message…'}
        disabled={disabled}
        className="flex-1 rounded-full border border-border px-4 py-2.5 text-sm outline-none focus:border-primary"
      />
      <button
        onClick={submit}
        disabled={disabled || !value.trim()}
        className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-primary text-white disabled:opacity-40"
        aria-label="Send"
      >
        <Send className="h-4 w-4" />
      </button>
    </div>
  )
}
