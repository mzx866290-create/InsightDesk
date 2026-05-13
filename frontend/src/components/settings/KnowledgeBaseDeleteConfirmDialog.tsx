import React from 'react'
import { AlertCircle, Loader2 } from 'lucide-react'

export type KnowledgeBaseDeleteConfirmState =
  | { type: 'chunk'; id: string; label: string }
  | { type: 'source'; source: string }
  | null

interface KnowledgeBaseDeleteConfirmDialogProps {
  confirmDelete: KnowledgeBaseDeleteConfirmState
  deletingChunk: string | null
  deletingSource: string | null
  onCancel: () => void
  onConfirmChunk: (chunkId: string) => void
  onConfirmSource: (source: string) => void
}

export const KnowledgeBaseDeleteConfirmDialog: React.FC<KnowledgeBaseDeleteConfirmDialogProps> = ({
  confirmDelete,
  deletingChunk,
  deletingSource,
  onCancel,
  onConfirmChunk,
  onConfirmSource,
}) => {
  if (!confirmDelete) {
    return null
  }

  const isSource = confirmDelete.type === 'source'
  const isDeleting = isSource
    ? deletingSource === confirmDelete.source
    : deletingChunk === confirmDelete.id

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4"
      onClick={onCancel}
      data-testid="kb-delete-confirm-dialog"
    >
      <div className="absolute inset-0 bg-black/50" />
      <div
        className="relative z-10 bg-bg-secondary border border-bg-border rounded-xl p-5 max-w-sm w-full shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 mb-3">
          <AlertCircle size={16} className="text-accent-red" />
          <h3 className="text-sm font-semibold text-text-primary">
            {isSource ? '删除整个文档' : '删除分块'}
          </h3>
        </div>
        <p className="text-xs text-text-secondary mb-4">
          {isSource
            ? `确定要删除文档「${confirmDelete.source}」的所有分块吗？此操作不可撤销。`
            : `确定要删除分块「${confirmDelete.label}...」吗？此操作不可撤销。`
          }
        </p>
        <div className="flex gap-2 justify-end">
          <button
            data-testid="kb-delete-confirm-cancel"
            onClick={onCancel}
            disabled={isDeleting}
            className="px-3 py-1.5 text-xs rounded-lg border border-bg-border text-text-secondary hover:bg-bg-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            取消
          </button>
          <button
            data-testid="kb-delete-confirm-submit"
            onClick={() => {
              if (isSource) onConfirmSource(confirmDelete.source)
              else onConfirmChunk(confirmDelete.id)
            }}
            disabled={isDeleting}
            className="px-3 py-1.5 text-xs rounded-lg bg-accent-red text-white hover:bg-accent-red/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
          >
            {isDeleting ? <Loader2 size={11} className="animate-spin" /> : null}
            确认删除
          </button>
        </div>
      </div>
    </div>
  )
}
