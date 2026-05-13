import React from 'react'

import type { KnowledgeBaseChunk } from '../../api/client'
import type { ChunkPagination } from './kbMonitorModel'
import { KbChunkList } from './KbChunkList'
import { KbChunkPagination } from './KbChunkPagination'
import { KbChunkSearchBar } from './KbChunkSearchBar'

export interface KbChunkBrowserProps {
  chunks: KnowledgeBaseChunk[]
  loading: boolean
  query: string
  sourceFilter: string
  sourceOptions: string[]
  pagination: ChunkPagination
  offset: number
  total: number
  editingChunkId: string | null
  editingChunkContent: string
  editingChunkSource: string
  savingChunkId: string | null
  deleteConfirmId: string | null
  deletingChunkId: string | null
  onQueryChange: (value: string) => void
  onSourceFilterChange: (value: string) => void
  onEditingContentChange: (value: string) => void
  onEditingSourceChange: (value: string) => void
  onSearch: () => void
  onRefresh: () => void
  onPreviousPage: () => void
  onNextPage: () => void
  onStartEdit: (chunk: KnowledgeBaseChunk) => void
  onCancelEdit: () => void
  onSave: () => void
  onDelete: (chunkId: string) => void
}

export function KbChunkBrowser({
  chunks,
  loading,
  query,
  sourceFilter,
  sourceOptions,
  pagination,
  offset,
  total,
  editingChunkId,
  editingChunkContent,
  editingChunkSource,
  savingChunkId,
  deleteConfirmId,
  deletingChunkId,
  onQueryChange,
  onSourceFilterChange,
  onEditingContentChange,
  onEditingSourceChange,
  onSearch,
  onRefresh,
  onPreviousPage,
  onNextPage,
  onStartEdit,
  onCancelEdit,
  onSave,
  onDelete,
}: KbChunkBrowserProps) {
  return (
    <div className="border-t border-bg-border pt-4">
      <KbChunkSearchBar
        loading={loading}
        query={query}
        sourceFilter={sourceFilter}
        sourceOptions={sourceOptions}
        onQueryChange={onQueryChange}
        onSourceFilterChange={onSourceFilterChange}
        onSearch={onSearch}
        onRefresh={onRefresh}
      />

      <KbChunkList
        chunks={chunks}
        loading={loading}
        editingChunkId={editingChunkId}
        editingChunkContent={editingChunkContent}
        editingChunkSource={editingChunkSource}
        savingChunkId={savingChunkId}
        deleteConfirmId={deleteConfirmId}
        deletingChunkId={deletingChunkId}
        onEditingContentChange={onEditingContentChange}
        onEditingSourceChange={onEditingSourceChange}
        onStartEdit={onStartEdit}
        onCancelEdit={onCancelEdit}
        onSave={onSave}
        onDelete={onDelete}
      />

      <KbChunkPagination
        pagination={pagination}
        offset={offset}
        total={total}
        loading={loading}
        onPreviousPage={onPreviousPage}
        onNextPage={onNextPage}
      />
    </div>
  )
}
