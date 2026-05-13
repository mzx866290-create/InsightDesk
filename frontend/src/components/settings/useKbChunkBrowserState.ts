import { useCallback, useMemo, useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'

import { getKnowledgeBaseChunks } from '../../api/client'
import type { KnowledgeBaseChunk } from '../../api/client'
import { EMPTY_CHUNK_FILTERS } from './kbChunkBrowserControllerModel'
import type {
  ChunkDeleteState,
  ChunkEditingState,
  ChunkFilterState,
  ChunkListState,
} from './kbChunkBrowserControllerModel'
import { createChunkLoadRequest } from './kbMonitorModel'
import type { ChunkLoadParams, ChunkSearchFilters } from './kbMonitorModel'

export function useKbChunkListState(setActionError: (message: string | null) => void) {
  const [chunks, setChunks] = useState<KnowledgeBaseChunk[]>([])
  const [loadingChunks, setLoadingChunks] = useState(false)
  const [chunkOffset, setChunkOffset] = useState(0)
  const [chunkTotal, setChunkTotal] = useState(0)

  const loadChunks = useCallback(
    async (params?: ChunkLoadParams) => {
      setLoadingChunks(true)
      setActionError(null)
      try {
        const data = await getKnowledgeBaseChunks(createChunkLoadRequest(params))
        setChunks(data.items)
        setChunkOffset(data.offset)
        setChunkTotal(data.total)
      } catch (error) {
        setActionError((error as Error).message)
        setChunks([])
        setChunkTotal(0)
        setChunkOffset(0)
      } finally {
        setLoadingChunks(false)
      }
    },
    [setActionError],
  )

  const resetChunkList = useCallback(() => {
    setChunks([])
    setChunkTotal(0)
    setChunkOffset(0)
  }, [])

  const listState = useMemo<ChunkListState>(
    () => ({
      chunks,
      loadingChunks,
      chunkOffset,
      chunkTotal,
    }),
    [chunkOffset, chunkTotal, chunks, loadingChunks],
  )

  return {
    listState,
    loadChunks,
    resetChunkList,
  }
}

export function useKbChunkFilterState() {
  const [chunkQuery, setChunkQuery] = useState('')
  const [chunkSourceFilter, setChunkSourceFilter] = useState('')
  const [appliedChunkQuery, setAppliedChunkQuery] = useState('')
  const [appliedChunkSourceFilter, setAppliedChunkSourceFilter] = useState('')

  const appliedChunkFilters = useMemo<ChunkSearchFilters>(
    () => ({
      query: appliedChunkQuery,
      source: appliedChunkSourceFilter,
    }),
    [appliedChunkQuery, appliedChunkSourceFilter],
  )

  const resetAppliedChunkFilters = useCallback(() => {
    setAppliedChunkQuery(EMPTY_CHUNK_FILTERS.query)
    setAppliedChunkSourceFilter(EMPTY_CHUNK_FILTERS.source)
  }, [])

  const applyChunkSearchFilters = useCallback((query: string, source: string) => {
    setAppliedChunkQuery(query)
    setAppliedChunkSourceFilter(source)
  }, [])

  const filterState = useMemo<ChunkFilterState>(
    () => ({
      chunkQuery,
      chunkSourceFilter,
      appliedChunkFilters,
    }),
    [appliedChunkFilters, chunkQuery, chunkSourceFilter],
  )

  return {
    filterState,
    setChunkQuery,
    setChunkSourceFilter,
    applyChunkSearchFilters,
    resetAppliedChunkFilters,
  }
}

export function useKbChunkEditingState(): ChunkEditingState & {
  setEditingChunkContent: Dispatch<SetStateAction<string>>
  setEditingChunkSource: Dispatch<SetStateAction<string>>
  setSavingChunkId: Dispatch<SetStateAction<string | null>>
  startEdit: (chunk: KnowledgeBaseChunk) => void
  cancelEdit: () => void
} {
  const [editingChunkId, setEditingChunkId] = useState<string | null>(null)
  const [editingChunkContent, setEditingChunkContent] = useState('')
  const [editingChunkSource, setEditingChunkSource] = useState('')
  const [savingChunkId, setSavingChunkId] = useState<string | null>(null)

  const startEdit = useCallback((chunk: KnowledgeBaseChunk) => {
    setEditingChunkId(chunk.chunk_id)
    setEditingChunkContent(chunk.content)
    setEditingChunkSource(chunk.source)
  }, [])

  const cancelEdit = useCallback(() => {
    setEditingChunkId(null)
    setEditingChunkContent('')
    setEditingChunkSource('')
  }, [])

  return {
    editingChunkId,
    editingChunkContent,
    editingChunkSource,
    savingChunkId,
    setEditingChunkContent,
    setEditingChunkSource,
    setSavingChunkId,
    startEdit,
    cancelEdit,
  }
}

export function useKbChunkDeleteState(): ChunkDeleteState & {
  setDeleteChunkConfirmId: Dispatch<SetStateAction<string | null>>
  setDeletingChunkId: Dispatch<SetStateAction<string | null>>
} {
  const [deleteChunkConfirmId, setDeleteChunkConfirmId] = useState<string | null>(null)
  const [deletingChunkId, setDeletingChunkId] = useState<string | null>(null)

  return {
    deleteChunkConfirmId,
    deletingChunkId,
    setDeleteChunkConfirmId,
    setDeletingChunkId,
  }
}
