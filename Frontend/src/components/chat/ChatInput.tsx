import { useState, useRef, ChangeEvent } from 'react'
import { Send, Paperclip, Loader2 } from 'lucide-react'

interface ChatInputProps {
  onSend: (content: string) => void
  onFileSelected?: (file: File) => void
  disabled?: boolean
  uploadDisabled?: boolean
  isUploading?: boolean
  accept?: string
  placeholder?: string
}

export function ChatInput({
  onSend,
  onFileSelected,
  disabled,
  uploadDisabled,
  isUploading,
  accept = '.pdf,.docx,.doc,.txt,.md',
  placeholder,
}: ChatInputProps) {
  const [value, setValue] = useState('')
  const [fileError, setFileError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function submit() {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    setFileError(null)
  }

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return

    setFileError(null)
    if (onFileSelected) {
      onFileSelected(file)
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <div className="flex flex-col border-t border-border bg-card p-4">
      {fileError && (
        <div className="mb-2 text-xs font-medium text-red-500">
          {fileError}
        </div>
      )}
      <div className="flex items-center gap-2">
        {onFileSelected && (
          <>
            <input
              ref={fileInputRef}
              type="file"
              accept={accept}
              onChange={handleFileChange}
              className="hidden"
              disabled={disabled || uploadDisabled || isUploading}
              data-testid="chat-file-input"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled || uploadDisabled || isUploading}
              className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full border border-border text-muted hover:bg-muted/10 hover:text-text disabled:opacity-40"
              aria-label="Attach file"
              title="Attach document (.pdf, .docx, .txt, .md)"
            >
              {isUploading ? (
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
              ) : (
                <Paperclip className="h-4 w-4" />
              )}
            </button>
          </>
        )}

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
    </div>
  )
}

