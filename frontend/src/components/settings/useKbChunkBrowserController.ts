import { useCallback, useMemo } from 'react'

import {
  deleteKnowledgeBaseChunk,
  updateKnowledgeBaseChunk,
} from '../../api/client'
import type { KBHealthData } from '../../api/client'
import type { KbChunkBrowserProps } from './KbChunkBrowser'
import {
  EMPTY_CHUNK_FILTERS,
  createChunkBrowserProps,
} from './kbChunkBrowserControllerModel'
import {
  getAppliedChunkLoadParams,
  getChunkPagination,
  getChunkSaveValidationError,
  getNextOffsetAfterChunkDelete,
  getTrimmedChunkSearchFilters,
  KB_CHUNK_DELETE_CONFIRM_TIMEOUT_MS,
  shouldRequestChunkDeleteConfirmation,
} from './kbMonitorModel'
import type { ChunkLoadParams } from './kbMonitorModel'
import {
  useKbChunkDeleteState,
  useKbChunkEditingState,
  useKbChunkFilterState,
  useKbChunkListState,
} from './useKbChunkBrowserState'

interface UseKbChunkBrowserControllerOptions {
  healthDocuments?: KBHealthData['documents']
  refreshHealth: () => Promise<void>
  setActionError: (message: string | null) => void
}

export interface KbChunkBrowserController {
  chunkBrowserProps: KbChunkBrowserProps
  loadChunks: (params?: ChunkLoadParams) => Promise<void>
  loadCurrentChunks: () => Promise<void>
  loadInitialChunks: () => void
  resetChunks: () => void
}

export function useKbChunkBrowserController({
  healthDocuments,
  refreshHealth,
  setActionError,
}: UseKbChunkBrowserControllerOptions): KbChunkBrowserController {
  const { listState, loadChunks, resetChunkList } = useKbChunkListState(setActionError)
  const {
    filterState,
    setChunkQuery,
    setChunkSourceFilter,
    applyChunkSearchFilters,
    resetAppliedChunkFilters,
  } = useKbChunkFilterState()
  const {
    editingChunkId,
    editingChunkContent,
    editingChunkSource,
    savingChunkId,
    setEditingChunkContent,
    setEditingChunkSource,
    setSavingChunkId,
    startEdit,
    cancelEdit,
  } = useKbChunkEditingState()
  const {
    deleteChunkConfirmId,
    deletingChunkId,
    setDeleteChunkConfirmId,
    setDeletingChunkId,
  } = useKbChunkDeleteState()
  const { chunks, loadingChunks, chunkOffset, chunkTotal } = listState
  const { chunkQuery, chunkSourceFilter, appliedChunkFilters } = filterState

  const loadCurrentChunks = useCallback(async () => {
    await loadChunks(getAppliedChunkLoadParams(chunkOffset, appliedChunkFilters))
  }, [appliedChunkFilters, chunkOffset, loadChunks])

  const loadInitialChunks = useCallback(() => {
    void loadChunks(getAppliedChunkLoadParams(0, EMPTY_CHUNK_FILTERS))
    resetAppliedChunkFilters()
  }, [loadChunks, resetAppliedChunkFilters])

  const resetChunks = useCallback(() => {
    resetChunkList()
    resetAppliedChunkFilters()
  }, [resetAppliedChunkFilters, resetChunkList])

  const handleChunkSearch = useCallback(() => {
    const { query, source } = getTrimmedChunkSearchFilters(chunkQuery, chunkSourceFilter)
    applyChunkSearchFilters(query, source)
    void loadChunks({ offset: 0, query, source })
  }, [applyChunkSearchFilters, chunkQuery, chunkSourceFilter, loadChunks])

  const handleSaveChunk = useCallback(async () => {
    if (!editingChunkId) return
    const validationError = getChunkSaveValidationError(editingChunkContent, editingChunkSource)
    if (validationError) {
      setActionError(validationError)
      return
    }

    setSavingChunkId(editingChunkId)
    setActionError(null)
    try {
      await updateKnowledgeBaseChunk(editingChunkId, {
        content: editingChunkContent,
        source: editingChunkSource,
      })
      cancelEdit()
      await loadCurrentChunks()
      await refreshHealth()
    } catch (error) {
      setActionError((error as Error).message)
    } finally {
      setSavingChunkId(null)
    }
  }, [
    editingChunkContent,
    editingChunkId,
    editingChunkSource,
    cancelEdit,
    loadCurrentChunks,
    refreshHealth,
    setActionError,
  ])

  const handleDeleteChunk = useCallback(
    async (chunkId: string) => {
      if (shouldRequestChunkDeleteConfirmation(deleteChunkConfirmId, chunkId)) {
        setDeleteChunkConfirmId(chunkId)
        window.setTimeout(() => {
          setDeleteChunkConfirmId((current) => (current === chunkId ? null : current))
        }, KB_CHUNK_DELETE_CONFIRM_TIMEOUT_MS)
        return
      }

      setDeletingChunkId(chunkId)
      setActionError(null)
      setDeleteChunkConfirmId(null)
      try {
        await deleteKnowledgeBaseChunk(chunkId)
        const nextOffset = getNextOffsetAfterChunkDelete(chunkOffset, chunks.length)
        await loadChunks(getAppliedChunkLoadParams(nextOffset, appliedChunkFilters))
        await refreshHealth()
      } catch (error) {
        setActionError((error as Error).message)
      } finally {
        setDeletingChunkId(null)
      }
    },
    [
      appliedChunkFilters,
      chunkOffset,
      chunks.length,
      deleteChunkConfirmId,
      loadChunks,
      refreshHealth,
      setActionError,
    ],
  )

  const chunkPagination = useMemo(
    () => getChunkPagination(chunkTotal, chunkOffset),
    [chunkOffset, chunkTotal],
  )

  const handleRefreshChunks = useCallback(() => {
    void loadCurrentChunks()
  }, [loadCurrentChunks])

  const handlePreviousChunkPage = useCallback(() => {
    void loadChunks(getAppliedChunkLoadParams(chunkPagination.previousOffset, appliedChunkFilters))
  }, [appliedChunkFilters, chunkPagination.previousOffset, loadChunks])

  const handleNextChunkPage = useCallback(() => {
    void loadChunks(getAppliedChunkLoadParams(chunkPagination.nextOffset, appliedChunkFilters))
  }, [appliedChunkFilters, chunkPagination.nextOffset, loadChunks])

  const chunkBrowserProps = useMemo<KbChunkBrowserProps>(
    () =>
      createChunkBrowserProps({
        listState,
        filterState,
        pagination: chunkPagination,
        editingState: {
          editingChunkId,
          editingChunkContent,
          editingChunkSource,
          savingChunkId,
        },
        deleteState: {
          deleteChunkConfirmId,
          deletingChunkId,
        },
        healthDocuments,
        handlers: {
          setChunkQuery,
          setChunkSourceFilter,
          setEditingChunkContent,
          setEditingChunkSource,
          handleChunkSearch,
          handleRefreshChunks,
          handlePreviousChunkPage,
          handleNextChunkPage,
          startEdit,
          cancelEdit,
          handleSaveChunk,
          handleDeleteChunk,
        },
      }),
    [
      chunkPagination,
      deleteChunkConfirmId,
      deletingChunkId,
      editingChunkContent,
      editingChunkId,
      editingChunkSource,
      cancelEdit,
      handleChunkSearch,
      handleDeleteChunk,
      handleNextChunkPage,
      handlePreviousChunkPage,
      handleRefreshChunks,
      handleSaveChunk,
      healthDocuments,
      filterState,
      listState,
      savingChunkId,
      startEdit,
    ],
  )

  return {
    chunkBrowserProps,
    loadChunks,
    loadCurrentChunks,
    loadInitialChunks,
    resetChunks,
  }
}
