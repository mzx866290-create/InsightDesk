import React from 'react'
import { FileText, X } from 'lucide-react'

interface KbUploadFileListProps {
  files: File[]
  onRemoveFile: (name: string) => void
}

export const KbUploadFileList: React.FC<KbUploadFileListProps> = ({
  files,
  onRemoveFile,
}) => {
  if (!files.length) return null

  return (
    <div className="space-y-1.5">
      {files.map(file => (
        <div key={file.name} className="flex items-center gap-2 px-3 py-2 bg-bg-tertiary rounded-lg border border-bg-border">
          <FileText size={13} className="text-accent-blue shrink-0" />
          <span className="flex-1 text-sm text-text-primary truncate">{file.name}</span>
          <span className="text-xs text-text-muted shrink-0">{(file.size / 1024).toFixed(0)} KB</span>
          <button onClick={() => onRemoveFile(file.name)} className="p-1 rounded text-text-muted hover:text-accent-red transition-colors">
            <X size={11} />
          </button>
        </div>
      ))}
    </div>
  )
}
