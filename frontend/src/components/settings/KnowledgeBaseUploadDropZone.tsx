import React, { useRef } from 'react'
import { Upload } from 'lucide-react'

export const KNOWLEDGE_BASE_UPLOAD_ACCEPTED_TYPES = '.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.md,.png,.jpg,.jpeg,.webp'

interface KnowledgeBaseUploadDropZoneProps {
  dragging: boolean
  onDraggingChange: (dragging: boolean) => void
  onDrop: (event: React.DragEvent<HTMLElement>) => void
  onSelectFiles: (files: FileList) => void
}

export const KnowledgeBaseUploadDropZone: React.FC<KnowledgeBaseUploadDropZoneProps> = ({
  dragging,
  onDraggingChange,
  onDrop,
  onSelectFiles,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null)

  return (
    <div
      data-testid="settings-kb-upload-zone"
      onDragOver={(event) => {
        event.preventDefault()
        onDraggingChange(true)
      }}
      onDragLeave={() => onDraggingChange(false)}
      onDrop={onDrop}
      onClick={() => fileInputRef.current?.click()}
      className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
        dragging ? 'border-accent-blue bg-accent-blue/5' : 'border-bg-border hover:border-accent-blue/50 hover:bg-bg-hover'
      }`}
    >
      <Upload size={24} className="mx-auto mb-3 text-text-muted" />
      <p className="text-sm text-text-secondary font-medium">点击选择文件或拖拽到此处</p>
      <p className="text-xs text-text-muted mt-1">支持 PDF、Word、Excel、CSV、TXT、Markdown、图片</p>
      <input
        data-testid="settings-kb-upload-input"
        ref={fileInputRef}
        type="file"
        multiple
        accept={KNOWLEDGE_BASE_UPLOAD_ACCEPTED_TYPES}
        className="hidden"
        onChange={(event) => {
          if (event.target.files) onSelectFiles(event.target.files)
        }}
      />
    </div>
  )
}
