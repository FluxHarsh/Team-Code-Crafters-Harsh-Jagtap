import { useState, useRef, useCallback } from 'react'
import { cn } from '@/lib/utils'

interface UploadedFile {
  name: string
  status: 'uploading' | 'done' | 'error'
  chars?: number
  error?: string
}

interface DocumentDropzoneProps {
  onUpload: (file: File) => Promise<{ filename: string; extracted_chars: number }>
  className?: string
}

export function DocumentDropzone({ onUpload, className }: DocumentDropzoneProps) {
  const [dragging, setDragging] = useState(false)
  const [files, setFiles] = useState<UploadedFile[]>([])
  const inputRef = useRef<HTMLInputElement>(null)

  const processFile = useCallback(
    async (file: File) => {
      const allowed = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain', 'text/markdown']
      if (!allowed.includes(file.type) && !file.name.match(/\.(pdf|docx|txt|md)$/i)) {
        setFiles((prev) => [
          ...prev,
          { name: file.name, status: 'error', error: 'Unsupported file type' },
        ])
        return
      }

      setFiles((prev) => [...prev, { name: file.name, status: 'uploading' }])
      try {
        const result = await onUpload(file)
        setFiles((prev) =>
          prev.map((f) =>
            f.name === file.name
              ? { ...f, status: 'done', chars: result.extracted_chars }
              : f
          )
        )
      } catch {
        setFiles((prev) =>
          prev.map((f) =>
            f.name === file.name
              ? { ...f, status: 'error', error: 'Upload failed' }
              : f
          )
        )
      }
    },
    [onUpload]
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragging(false)
      Array.from(e.dataTransfer.files).forEach(processFile)
    },
    [processFile]
  )

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    Array.from(e.target.files ?? []).forEach(processFile)
    e.target.value = ''
  }

  return (
    <div className={cn('space-y-2', className)}>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={cn(
          'flex flex-col items-center justify-center gap-1.5 border-2 border-dashed rounded-[12px] px-4 py-4 cursor-pointer transition',
          dragging
            ? 'border-primary bg-primary-soft'
            : 'border-border bg-bg hover:border-muted-2'
        )}
      >
        <span className="text-xl">📎</span>
        <p className="text-xs font-600 text-muted">
          Drop a file or <span className="text-primary">browse</span>
        </p>
        <p className="text-[10px] text-muted-2">PDF, DOCX, TXT, MD</p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt,.md"
          multiple
          onChange={handleChange}
          className="hidden"
        />
      </div>

      {files.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {files.map((f, i) => (
            <div
              key={i}
              className={cn(
                'flex items-center gap-1.5 text-xs font-600 px-2.5 py-1 rounded-[7px] border',
                f.status === 'done' && 'bg-success-soft border-green-200 text-success-dark',
                f.status === 'uploading' && 'bg-border-soft border-border text-muted',
                f.status === 'error' && 'bg-danger-soft border-red-200 text-danger'
              )}
            >
              {f.status === 'uploading' && (
                <span className="w-2.5 h-2.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
              )}
              {f.status === 'done' && <span>✓</span>}
              {f.status === 'error' && <span>✕</span>}
              <span className="truncate max-w-[120px]">{f.name}</span>
              {f.status === 'done' && f.chars && (
                <span className="opacity-60">{(f.chars / 1000).toFixed(1)}k chars</span>
              )}
              {f.status === 'error' && f.error && (
                <span className="opacity-80">{f.error}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
