import type { Dispatch, SetStateAction } from 'react'

import type { KBHealthData, KnowledgeBaseChunk } from '../../api/client'
import type { KbChunkBrowserProps } from './KbChunkBrowser'
import type { ChunkPagination, ChunkSearchFilters } from './kbMonitorModel'

export const EMPTY_CHUNK_FILTERS: ChunkSearchFilters = { query: '', source: '' }

export interface ChunkListState {
  chunks: KnowledgeBaseChunk[]
  loadingChunks: boolean
  chunkOffset: number
  chunkTotal: number
}

export interface ChunkFilterState {
  chunkQuery: string
  chunkSourceFilter: string
  appliedChunkFilters: ChunkSearchFilters
}

export interface ChunkEditingState {
  editingChunkId: string | null
  editingChunkContent: string
  editingChunkSource: string
  savingChunkId: string | null
}

export interface ChunkDeleteState {
  deleteChunkConfirmId: string | null
  deletingChunkId: string | null
}

export interface ChunkBrowserActionHandlers {
  setChunkQuery: Dispatch<SetStateAction<string>>
  setChunkSourceFilter: Dispatch<SetStateAction<string>>
  setEditingChunkContent: Dispatch<SetStateAction<string>>
  setEditingChunkSource: Dispatch<SetStateAction<string>>
  handleChunkSearch: () => void
  handleRefreshChunks: () => void
  handlePreviousChunkPage: () => void
  handleNextChunkPage: () => void
  startEdit: (chunk: KnowledgeBaseChunk) => void
  cancelEdit: () => void
  handleSaveChunk: () => void
  handleDeleteChunk: (chunkId: string) => void
}

export interface CreateChunkBrowserPropsOptions {
  listState: ChunkListState
  filterState: ChunkFilterState
  pagination: ChunkPagination
  editingState: ChunkEditingState
  deleteState: ChunkDeleteState
  healthDocuments?: KBHealthData['documents']
  handlers: ChunkBrowserActionHandlers
}

export function createChunkBrowserProps({
  listState,
  filterState,
  pagination,
  editingState,
  deleteState,
  healthDocuments,
  handlers,
}: CreateChunkBrowserPropsOptions): KbChunkBrowserProps {
  return {
    chunks: listState.chunks,
    loading: listState.loadingChunks,
    query: filterState.chunkQuery,
    sourceFilter: filterState.chunkSourceFilter,
    sourceOptions: healthDocuments?.map((doc) => doc.name) ?? [],
    pagination,
    offset: listState.chunkOffset,
    total: listState.chunkTotal,
    editingChunkId: editingState.editingChunkId,
    editingChunkContent: editingState.editingChunkContent,
    editingChunkSource: editingState.editingChunkSource,
    savingChunkId: editingState.savingChunkId,
    deleteConfirmId: deleteState.deleteChunkConfirmId,
    deletingChunkId: deleteState.deletingChunkId,
    onQueryChange: handlers.setChunkQuery,
    onSourceFilterChange: handlers.setChunkSourceFilter,
    onEditingContentChange: handlers.setEditingChunkContent,
    onEditingSourceChange: handlers.setEditingChunkSource,
    onSearch: handlers.handleChunkSearch,
    onRefresh: handlers.handleRefreshChunks,
    onPreviousPage: handlers.handlePreviousChunkPage,
    onNextPage: handlers.handleNextChunkPage,
    onStartEdit: handlers.startEdit,
    onCancelEdit: handlers.cancelEdit,
    onSave: handlers.handleSaveChunk,
    onDelete: handlers.handleDeleteChunk,
  }
}
