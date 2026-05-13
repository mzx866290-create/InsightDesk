import React from 'react'

import type { KnowledgeBaseChunk } from '../../api/client'
import { KbChunkListItem } from './KbChunkListItem'

export interface KbChunkListProps {
  chunks: KnowledgeBaseChunk[]
  loading: boolean
  editingChunkId: string | null
  editingChunkContent: string
  editingChunkSource: string
  savingChunkId: string | null
  deleteConfirmId: string | null
  deletingChunkId: string | null
  onEditingContentChange: (value: string) => void
  onEditingSourceChange: (value: string) => void
  onStartEdit: (chunk: KnowledgeBaseChunk) => void
  onCancelEdit: () => void
  onSave: () => void
  onDelete: (chunkId: string) => void
}

export const KbChunkList: React.FC<KbChunkListProps> = ({
  chunks,
  loading,
  editingChunkId,
  editingChunkContent,
  editingChunkSource,
  savingChunkId,
  deleteConfirmId,
  deletingChunkId,
  onEditingContentChange,
  onEditingSourceChange,
  onStartEdit,
  onCancelEdit,
  onSave,
  onDelete,
}) => (
  <>
    {loading && (
      <div className="flex justify-center py-5">
        <span className="w-5 h-5 border-2 border-accent-blue border-t-transparent rounded-full animate-spin" />
      </div>
    )}

    {!loading && chunks.length === 0 && (
      <div
        className="rounded-lg border border-bg-border bg-bg-tertiary/40 px-3 py-5 text-center text-xs text-text-secondary"
        data-testid="settings-kb-chunk-empty"
      >
        瑜版挸澧犵粵娑⑩偓澶嬫蒋娴犳湹绗呭▽鈩冩箒閸掑洨澧栭弫鐗堝祦閵?
      </div>
    )}

    {!loading && chunks.length > 0 && (
      <div className="space-y-2" data-testid="settings-kb-chunk-list">
        {chunks.map((chunk) => (
          <KbChunkListItem
            key={chunk.chunk_id}
            chunk={chunk}
            isEditing={editingChunkId === chunk.chunk_id}
            editingContent={editingChunkContent}
            editingSource={editingChunkSource}
            isSaving={savingChunkId === chunk.chunk_id}
            isDeleteConfirming={deleteConfirmId === chunk.chunk_id}
            isDeleting={deletingChunkId === chunk.chunk_id}
            onEditingContentChange={onEditingContentChange}
            onEditingSourceChange={onEditingSourceChange}
            onStartEdit={onStartEdit}
            onCancelEdit={onCancelEdit}
            onSave={onSave}
            onDelete={onDelete}
          />
        ))}
      </div>
    )}
  </>
)
