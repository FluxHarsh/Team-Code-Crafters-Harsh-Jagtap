import { useCallback, useRef, useState } from 'react'
import { UploadCloud, FileText, X } from 'lucide-react'
import { cn } from '@/lib/utils'

// v2: File Intake Agent also supports PPT and images — the old list
// (pdf/docx/txt/md only) silently rejected those client-side before they
// ever reached the backend.
const ACCEPTED_EXTENSIONS = [
  '.pdf', '.docx', '.doc', '.txt', '.md',
  '.ppt', '.pptx',
  '.png', '.jpg', '.jpeg', '.webp', '.gif',
]

const ACCEPTED_MIME_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/msword',
  'text/plain',
  'text/markdown',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/vnd.ms-powerpoint',
  'image/png',
  'image/jpeg',
  'image/webp',
  'image/gif',
]

interface DocumentDropzoneProps {
  onFileSelected: (file: File) => void
  disabled?: boolean
  multiple?: boolean
}

function isAcceptedFile(file: File): boolean {
  const name = file.name.toLowerCase()
  const extOk = ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))
  const mimeOk = file.type ? ACCEPTED_MIME_TYPES.includes(file.type) : false
  // Some browsers/OSes don't set a MIME type for certain files — fall back
  // to extension check so valid files aren't rejected.
  return extOk || mimeOk
}

export function DocumentDropzone({ onFileSelected, disabled, multiple }: DocumentDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFiles = useCallback(
    (fileList: FileList | null) => {
      if (!fileList || fileList.length === 0) return
      setError(null)
      const files = Array.from(fileList)
      for (const file of files) {
        if (!isAcceptedFile(file)) {
          setError(`"${file.name}" isn't a supported file type (PDF, Word, PPT, TXT, MD, or image).`)
          continue
        }
        onFileSelected(file)
        if (!multiple) break
      }
    },
    [onFileSelected, multiple]
  )

  return (
    <div>
      <div
        className={cn(
          'flex flex-col items-center justify-center gap-2 rounded-card border-2 border-dashed p-8 text-center transition-colors cursor-pointer',
          isDragging ? 'border-primary bg-primary-soft' : 'border-border-soft bg-bg',
          disabled && 'opacity-50 pointer-events-none'
        )}
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setIsDragging(false)
          handleFiles(e.dataTransfer.files)
        }}
        onClick={() => inputRef.current?.click()}
      >
        <UploadCloud className="h-6 w-6 text-muted" />
        <p className="text-sm text-text">
          <span className="font-medium text-primary">Click to upload</span> or drag and drop
        </p>
        <p className="text-xs text-muted">PDF, Word, PPT, TXT, MD, or images</p>
        <input
          ref={inputRef}
          type="file"
          multiple={multiple}
          accept={[...ACCEPTED_EXTENSIONS, ...ACCEPTED_MIME_TYPES].join(',')}
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
      {error && (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-danger">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-auto">
            <X className="h-3 w-3" />
          </button>
        </div>
      )}
    </div>
  )
}

export function FilePill({ filename, onRemove }: { filename: string; onRemove?: () => void }) {
  return (
    <div className="inline-flex items-center gap-1.5 rounded-full bg-navy-soft px-3 py-1 text-xs text-navy">
      <FileText className="h-3 w-3" />
      <span className="max-w-[160px] truncate">{filename}</span>
      {onRemove && (
        <button onClick={onRemove}>
          <X className="h-3 w-3" />
        </button>
      )}
    </div>
  )
}
