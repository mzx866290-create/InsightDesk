import React from 'react'
import { KbUploadFileList } from './KbUploadFileList'
import { KnowledgeBaseUploadActionButton } from './KnowledgeBaseUploadActionButton'
import { KnowledgeBaseUploadDropZone } from './KnowledgeBaseUploadDropZone'
import { KnowledgeBaseUploadTaskProgress } from './KnowledgeBaseUploadTaskProgress'
import { useKnowledgeBaseUploadController } from './useKnowledgeBaseUploadController'

interface KnowledgeBaseUploadTabProps {
  onUploaded?: () => void
  onAdminAccessError?: (message: string | null) => void
}

export const KnowledgeBaseUploadTab: React.FC<KnowledgeBaseUploadTabProps> = ({
  onUploaded,
  onAdminAccessError,
}) => {
  const {
    dragging,
    files,
    uploading,
    task,
    error,
    setDragging,
    addFiles,
    removeFile,
    handleDrop,
    handleUpload,
  } = useKnowledgeBaseUploadController({
    onUploaded,
    onAdminAccessError,
  })

  return (
    <div className="space-y-4">
      <KnowledgeBaseUploadDropZone
        dragging={dragging}
        onDraggingChange={setDragging}
        onDrop={handleDrop}
        onSelectFiles={addFiles}
      />

      <KbUploadFileList files={files} onRemoveFile={removeFile} />

      <KnowledgeBaseUploadTaskProgress task={task} />

      {error && (
        <div
          data-testid="settings-kb-upload-error"
          className="px-3 py-2 bg-accent-red/10 border border-accent-red/20 rounded-lg text-xs text-accent-red"
        >
          {error}
        </div>
      )}

      <KnowledgeBaseUploadActionButton
        uploading={uploading}
        disabled={!files.length || uploading}
        onClick={handleUpload}
      />
    </div>
  )
}
