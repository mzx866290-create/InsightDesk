import { describe, expect, it, vi } from 'vitest'

import type { KnowledgeBaseChunk } from '../../api/client'
import { createChunkBrowserProps } from './kbChunkBrowserControllerModel'

const chunk: KnowledgeBaseChunk = {
  chunk_id: 'chunk-1',
  position: 0,
  source: 'manual.md',
  content: 'Full chunk content',
  preview: 'Chunk preview',
  char_count: 18,
  metadata: {},
}

describe('kbChunkBrowserControllerModel', () => {
  it('maps controller state and handlers to stable browser props', () => {
    const handlers = {
      setChunkQuery: vi.fn(),
      setChunkSourceFilter: vi.fn(),
      setEditingChunkContent: vi.fn(),
      setEditingChunkSource: vi.fn(),
      handleChunkSearch: vi.fn(),
      handleRefreshChunks: vi.fn(),
      handlePreviousChunkPage: vi.fn(),
      handleNextChunkPage: vi.fn(),
      startEdit: vi.fn(),
      cancelEdit: vi.fn(),
      handleSaveChunk: vi.fn(),
      handleDeleteChunk: vi.fn(),
    }

    const props = createChunkBrowserProps({
      listState: {
        chunks: [chunk],
        loadingChunks: true,
        chunkOffset: 12,
        chunkTotal: 25,
      },
      filterState: {
        chunkQuery: 'incident',
        chunkSourceFilter: 'manual.md',
        appliedChunkFilters: { query: 'incident', source: 'manual.md' },
      },
      pagination: {
        currentPage: 2,
        totalPages: 3,
        previousOffset: 0,
        nextOffset: 24,
      },
      editingState: {
        editingChunkId: 'chunk-1',
        editingChunkContent: 'Draft content',
        editingChunkSource: 'manual.md',
        savingChunkId: 'chunk-1',
      },
      deleteState: {
        deleteChunkConfirmId: 'chunk-2',
        deletingChunkId: 'chunk-3',
      },
      healthDocuments: [{ name: 'manual.md', chunks: 1 }],
      handlers,
    })

    expect(props).toMatchObject({
      chunks: [chunk],
      loading: true,
      query: 'incident',
      sourceFilter: 'manual.md',
      sourceOptions: ['manual.md'],
      offset: 12,
      total: 25,
      editingChunkId: 'chunk-1',
      editingChunkContent: 'Draft content',
      editingChunkSource: 'manual.md',
      savingChunkId: 'chunk-1',
      deleteConfirmId: 'chunk-2',
      deletingChunkId: 'chunk-3',
    })
    expect(props.onQueryChange).toBe(handlers.setChunkQuery)
    expect(props.onSearch).toBe(handlers.handleChunkSearch)
    expect(props.onStartEdit).toBe(handlers.startEdit)
    expect(props.onDelete).toBe(handlers.handleDeleteChunk)
  })
})
