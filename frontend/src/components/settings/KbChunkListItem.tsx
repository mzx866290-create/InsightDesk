import React from 'react'
import { Pencil, Trash2 } from 'lucide-react'

import type { KnowledgeBaseChunk } from '../../api/client'
import { useI18n } from '../../i18n'
import { KbChunkEditForm } from './KbChunkEditForm'

export interface KbChunkListItemProps {
  chunk: KnowledgeBaseChunk
  isEditing: boolean
  editingContent: string
  editingSource: string
  isSaving: boolean
  isDeleteConfirming: boolean
  isDeleting: boolean
  onEditingContentChange: (value: string) => void
  onEditingSourceChange: (value: string) => void
  onStartEdit: (chunk: KnowledgeBaseChunk) => void
  onCancelEdit: () => void
  onSave: () => void
  onDelete: (chunkId: string) => void
}

export const KbChunkListItem: React.FC<KbChunkListItemProps> = ({
  chunk,
  isEditing,
  editingContent,
  editingSource,
  isSaving,
  isDeleteConfirming,
  isDeleting,
  onEditingContentChange,
  onEditingSourceChange,
  onStartEdit,
  onCancelEdit,
  onSave,
  onDelete,
}) => {
  const { t } = useI18n()
  const position = chunk.position >= 0 ? chunk.position + 1 : '-'
  const chunkSummary = t('settings.kbChunks.charCount')
    .replace('{position}', String(position))
    .replace('{count}', String(chunk.char_count))
  const deleteTitle = isDeleteConfirming
    ? t('settings.kbChunks.confirmDeleteTitle')
    : t('settings.kbChunks.deleteTitle')

  return (
    <div
      className="rounded-lg border border-bg-border bg-bg-tertiary/40 p-3"
      data-testid="settings-kb-chunk-item"
      data-chunk-id={chunk.chunk_id}
    >
    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
      <div className="min-w-0 flex-1">
        <p className="truncate text-[11px] font-medium text-accent-blue/80">
          {chunk.source || t('settings.kbChunks.unknownSource')}
        </p>
        <p className="text-[10px] text-text-secondary/70">
          {chunkSummary}
        </p>
      </div>
      <div className="flex items-center gap-1">
        {!isEditing && (
          <button
            type="button"
            onClick={() => onStartEdit(chunk)}
            className="flex min-h-11 min-w-11 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
            title={t('settings.kbChunks.editTitle')}
            aria-label={t('settings.kbChunks.editTitle')}
            data-testid="settings-kb-chunk-edit"
            data-chunk-id={chunk.chunk_id}
          >
            <Pencil size={12} />
          </button>
        )}
        <button
          type="button"
          onClick={() => onDelete(chunk.chunk_id)}
          disabled={isDeleting}
          className={`flex min-h-11 min-w-11 items-center justify-center rounded-md transition-colors disabled:opacity-50 ${
            isDeleteConfirming
              ? 'bg-accent-red/10 text-accent-red'
              : 'text-text-secondary hover:text-accent-red hover:bg-accent-red/10'
          }`}
          title={deleteTitle}
          aria-label={deleteTitle}
          data-testid="settings-kb-chunk-delete"
          data-chunk-id={chunk.chunk_id}
          data-confirming={isDeleteConfirming ? 'true' : 'false'}
        >
          {isDeleting ? (
            <span className="w-3.5 h-3.5 border border-current border-t-transparent rounded-full animate-spin block" />
          ) : (
            <Trash2 size={12} />
          )}
        </button>
      </div>
    </div>

    {isEditing ? (
      <KbChunkEditForm
        source={editingSource}
        content={editingContent}
        saving={isSaving}
        onSourceChange={onEditingSourceChange}
        onContentChange={onEditingContentChange}
        onSave={onSave}
        onCancel={onCancelEdit}
      />
    ) : (
      <p
        data-testid="settings-kb-chunk-preview"
        className="whitespace-pre-wrap break-words text-xs leading-relaxed text-text-secondary/85"
      >
        {chunk.preview}
      </p>
    )}
    </div>
  )
}
