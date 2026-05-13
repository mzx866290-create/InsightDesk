import React, { useRef, useState } from 'react'
import { Upload } from 'lucide-react'

export interface DocumentUploadZoneProps {
  uploading: boolean
  onUpload: (files: FileList | null) => void
}

export const DocumentUploadZone: React.FC<DocumentUploadZoneProps> = ({
  uploading,
  onUpload,
}) => {
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [dragOver, setDragOver] = useState(false)

  return (
    <div
      data-testid="settings-documents-upload-zone"
      className={`border-2 border-dashed rounded-xl p-6 text-center transition-colors cursor-pointer ${
        dragOver ? 'border-accent-blue bg-accent-blue/5' : 'border-bg-border hover:border-accent-blue/50'
      }`}
      onDragOver={(event) => {
        event.preventDefault()
        setDragOver(true)
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(event) => {
        event.preventDefault()
        setDragOver(false)
        onUpload(event.dataTransfer.files)
      }}
      onClick={() => fileInputRef.current?.click()}
    >
      <input
        data-testid="settings-documents-upload-input"
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.docx,.doc,.md,.csv,.txt,.xlsx,.xls"
        className="hidden"
        onChange={(event) => {
          onUpload(event.target.files)
          event.target.value = ''
        }}
      />
      {uploading ? (
        <div className="flex flex-col items-center gap-2">
          <span className="w-8 h-8 border-2 border-accent-blue border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-text-secondary">上传中...</p>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2">
          <Upload size={28} className="text-text-secondary/50" />
          <p className="text-sm text-text-primary">将文件拖到此处，或点击选择</p>
          <p className="text-xs text-text-secondary">支持 PDF、Word、Markdown、CSV、TXT、Excel（单个文件不超过 10 MB，大文件会自动分批处理）</p>
          <p className="text-xs text-text-secondary/60 mt-0.5">结构化文档会按章节智能切块，检索结果更完整</p>
        </div>
      )}
    </div>
  )
}
