import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  deleteKnowledgeBaseChunk,
  getKnowledgeBaseChunks,
  type KnowledgeBaseChunk,
} from '../../api/client'
import { isAdminAccessError } from '../admin/adminAccess'
import type { KnowledgeBaseDeleteConfirmState } from './KnowledgeBaseDeleteConfirmDialog'
import { groupChunksBySource, type DocGroup } from './knowledgeBaseModalModel'

const DOCUMENT_CHUNK_PAGE_SIZE = 200

interface UseKnowledgeBaseDocumentsControllerOptions {
  onDeleted?: () => void
  onAdminAccessError?: (message: string | null) => void
}

export interface KnowledgeBaseDocumentsController {
  loading: boolean
  error: string | null
  searchQuery: string
  filteredGroups: DocGroup[]
  expandedSources: ReadonlySet<string>
  deletingChunk: string | null
  deletingSource: string | null
  confirmDelete: KnowledgeBaseDeleteConfirmState
  isFiltering: boolean
  load: () => Promise<void>
  setSearchQuery: (query: string) => void
  toggleSource: (source: string) => void
  requestDeleteChunk: (chunkId: string, label: string) => void
  requestDeleteSource: (source: string) => void
  cancelDelete: () => void
  confirmDeleteChunk: (chunkId: string) => Promise<void>
  confirmDeleteSource: (source: string) => Promise<void>
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

export function useKnowledgeBaseDocumentsController({
  onDeleted,
  onAdminAccessError,
}: UseKnowledgeBaseDocumentsControllerOptions): KnowledgeBaseDocumentsController {
  const [loading, setLoading] = useState(true)
  const [groups, setGroups] = useState<DocGroup[]>([])
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set())
  const [deletingChunk, setDeletingChunk] = useState<string | null>(null)
  const [deletingSource, setDeletingSource] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<KnowledgeBaseDeleteConfirmState>(null)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      // Load every page so the document list is not capped by API pagination.
      const allChunks: KnowledgeBaseChunk[] = []
      let offset = 0
      while (true) {
        const res = await getKnowledgeBaseChunks({
          offset,
          limit: DOCUMENT_CHUNK_PAGE_SIZE,
        })
        allChunks.push(...res.items)
        if (!res.has_more) break
        offset += DOCUMENT_CHUNK_PAGE_SIZE
      }
      setGroups(groupChunksBySource(allChunks))
      onAdminAccessError?.(null)
    } catch (loadError: unknown) {
      const message = getErrorMessage(loadError, '加载失败')
      setError(message)
      if (isAdminAccessError(loadError)) onAdminAccessError?.(message)
    } finally {
      setLoading(false)
    }
  }, [onAdminAccessError])

  useEffect(() => {
    void load()
  }, [load])

  const toggleSource = useCallback((source: string) => {
    setExpandedSources(prev => {
      const next = new Set(prev)
      if (next.has(source)) next.delete(source)
      else next.add(source)
      return next
    })
  }, [])

  const requestDeleteChunk = useCallback((chunkId: string, label: string) => {
    setConfirmDelete({ type: 'chunk', id: chunkId, label })
  }, [])

  const requestDeleteSource = useCallback((source: string) => {
    setConfirmDelete({ type: 'source', source })
  }, [])

  const cancelDelete = useCallback(() => {
    setConfirmDelete(null)
  }, [])

  const confirmDeleteChunk = useCallback(
    async (chunkId: string) => {
      setDeletingChunk(chunkId)
      setConfirmDelete(null)
      try {
        await deleteKnowledgeBaseChunk(chunkId)
        await load()
        onDeleted?.()
      } catch (deleteError: unknown) {
        const message = getErrorMessage(deleteError, '删除失败')
        setError(message)
        if (isAdminAccessError(deleteError)) onAdminAccessError?.(message)
      } finally {
        setDeletingChunk(null)
      }
    },
    [load, onAdminAccessError, onDeleted],
  )

  const confirmDeleteSource = useCallback(
    async (source: string) => {
      const group = groups.find(item => item.source === source)
      if (!group) return

      setDeletingSource(source)
      setConfirmDelete(null)
      try {
        for (const chunk of group.chunks) {
          await deleteKnowledgeBaseChunk(chunk.chunk_id)
        }
        await load()
        onDeleted?.()
      } catch (deleteError: unknown) {
        const message = getErrorMessage(deleteError, '删除失败')
        setError(message)
        if (isAdminAccessError(deleteError)) onAdminAccessError?.(message)
      } finally {
        setDeletingSource(null)
      }
    },
    [groups, load, onAdminAccessError, onDeleted],
  )

  const filteredGroups = useMemo(() => {
    if (!searchQuery.trim()) return groups
    const normalizedQuery = searchQuery.toLowerCase()
    return groups.filter(group => group.source.toLowerCase().includes(normalizedQuery))
  }, [groups, searchQuery])

  return {
    loading,
    error,
    searchQuery,
    filteredGroups,
    expandedSources,
    deletingChunk,
    deletingSource,
    confirmDelete,
    isFiltering: Boolean(searchQuery),
    load,
    setSearchQuery,
    toggleSource,
    requestDeleteChunk,
    requestDeleteSource,
    cancelDelete,
    confirmDeleteChunk,
    confirmDeleteSource,
  }
}
