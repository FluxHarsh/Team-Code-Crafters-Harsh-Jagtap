import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fileUploadApi } from '@/api'
import { useStore } from '@/store'
import { DocumentDropzone, FilePill } from '@/components/shared/DocumentDropzone'
import { formatRelative } from '@/lib/utils'
import type { ProjectFile } from '@/types'

const STATUS_LABEL: Record<ProjectFile['status'], string> = {
  uploading: 'Uploading…',
  processing: 'Processing…',
  processed: 'Ready',
  failed: 'Failed',
}

export function FileUploadPanel({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient()
  const files = useStore((s) => s.files)
  const setFiles = useStore((s) => s.setFiles)
  const upsertFile = useStore((s) => s.upsertFile)

  const { data } = useQuery({
    queryKey: ['files', projectId],
    queryFn: () => fileUploadApi.list(projectId),
  })

  useEffect(() => {
    if (data) setFiles(data.files)
  }, [data, setFiles])

  const upload = useMutation({
    mutationFn: (file: File) => fileUploadApi.upload(projectId, file),
    onSuccess: (res) => {
      upsertFile(res.file)
      queryClient.invalidateQueries({ queryKey: ['files', projectId] })
    },
  })

  return (
    <div className="mx-auto max-w-2xl p-8">
      <h1 className="mb-1 text-lg font-semibold text-text">Files</h1>
      <p className="mb-6 text-sm text-muted">
        Upload specs, notes, or slides for the File Intake Agent to read.
      </p>

      <DocumentDropzone multiple onFileSelected={(file) => upload.mutate(file)} disabled={upload.isPending} />

      <div className="mt-6 space-y-2">
        {files.map((f) => (
          <div key={f.id} className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
            <FilePill filename={f.filename} />
            <span className="ml-auto text-xs text-muted">{STATUS_LABEL[f.status]}</span>
            {f.created_at && <span className="text-xs text-muted">{formatRelative(f.created_at)}</span>}
          </div>
        ))}
      </div>
    </div>
  )
}
