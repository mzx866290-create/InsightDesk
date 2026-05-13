import { useCallback, useState } from 'react'

import {
  deleteKnowledgeBase as deleteKnowledgeBaseRequest,
  getKBHealth,
  testKBRetrieval,
} from '../../api/client'
import type { KBHealthData, RetrievalTestResult } from '../../api/client'
import {
  createRetrievalTestOptions,
  getKnowledgeBaseDeleteTargetPath,
  KB_DELETE_CONFIRM_TIMEOUT_MS,
  KNOWLEDGE_BASE_DELETE_FAILED_PREFIX,
  shouldRequestKnowledgeBaseDeleteConfirmation,
} from './kbMonitorModel'
import type {
  ChunkLoadParams,
  DeleteKnowledgeBaseResult,
  RetrievalTestSettings,
} from './kbMonitorModel'

interface UseKbHealthLoaderResult {
  health: KBHealthData | null
  loadingHealth: boolean
  actionError: string | null
  setActionError: (message: string | null) => void
  setHealth: (health: KBHealthData | null) => void
  refreshHealth: () => Promise<void>
}

export function useKbHealthLoader(): UseKbHealthLoaderResult {
  const [health, setHealth] = useState<KBHealthData | null>(null)
  const [loadingHealth, setLoadingHealth] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const refreshHealth = useCallback(async () => {
    setLoadingHealth(true)
    setActionError(null)
    try {
      const nextHealth = await getKBHealth()
      setHealth(nextHealth)
      setActionError(null)
    } catch (error) {
      setActionError((error as Error).message)
      setHealth(null)
    } finally {
      setLoadingHealth(false)
    }
  }, [])

  return {
    health,
    loadingHealth,
    actionError,
    setActionError,
    setHealth,
    refreshHealth,
  }
}

interface UseKbRetrievalTestActionsOptions {
  query: string
  settings: RetrievalTestSettings
}

interface UseKbRetrievalTestActionsResult {
  result: RetrievalTestResult | null
  loading: boolean
  runTest: () => Promise<void>
}

export function useKbRetrievalTestActions({
  query,
  settings,
}: UseKbRetrievalTestActionsOptions): UseKbRetrievalTestActionsResult {
  const [result, setResult] = useState<RetrievalTestResult | null>(null)
  const [loading, setLoading] = useState(false)

  const runTest = useCallback(async () => {
    if (!query.trim()) return

    setLoading(true)
    setResult(null)
    try {
      const nextResult = await testKBRetrieval(query, createRetrievalTestOptions(settings))
      setResult(nextResult)
    } catch (error) {
      setResult({ results_count: 0, latency_ms: 0, error: (error as Error).message })
    } finally {
      setLoading(false)
    }
  }, [query, settings])

  return {
    result,
    loading,
    runTest,
  }
}

interface UseKnowledgeBaseDeleteActionOptions {
  loadChunks: (params?: ChunkLoadParams) => Promise<void>
  onKnowledgeBasesChanged: () => Promise<void> | void
  refreshHealth: () => Promise<void>
  resetChunks: () => void
  setActionError: (message: string | null) => void
  setHealth: (health: KBHealthData | null) => void
}

interface UseKnowledgeBaseDeleteActionResult {
  deleting: boolean
  deleteKnowledgeBase: (path?: string) => Promise<DeleteKnowledgeBaseResult>
  isConfirming: (path?: string) => boolean
}

export function useKnowledgeBaseDeleteAction({
  loadChunks,
  onKnowledgeBasesChanged,
  refreshHealth,
  resetChunks,
  setActionError,
  setHealth,
}: UseKnowledgeBaseDeleteActionOptions): UseKnowledgeBaseDeleteActionResult {
  const [deleting, setDeleting] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [confirmingPath, setConfirmingPath] = useState<string | null>(null)

  const deleteKnowledgeBase = useCallback(
    async (path?: string): Promise<DeleteKnowledgeBaseResult> => {
      const targetPath = getKnowledgeBaseDeleteTargetPath(path)
      if (shouldRequestKnowledgeBaseDeleteConfirmation(confirming, confirmingPath, path)) {
        setConfirming(true)
        setConfirmingPath(targetPath)
        window.setTimeout(() => {
          setConfirming(false)
          setConfirmingPath(null)
        }, KB_DELETE_CONFIRM_TIMEOUT_MS)
        return 'confirmation_requested'
      }

      setDeleting(true)
      setActionError(null)
      setConfirming(false)
      setConfirmingPath(null)
      try {
        await deleteKnowledgeBaseRequest(path)
        setHealth(null)
        resetChunks()
        await onKnowledgeBasesChanged()
        await refreshHealth()
        await loadChunks({ offset: 0, query: '', source: '' })
        return 'deleted'
      } catch (error) {
        setActionError(`${KNOWLEDGE_BASE_DELETE_FAILED_PREFIX}${(error as Error).message}`)
        return 'failed'
      } finally {
        setDeleting(false)
      }
    },
    [
      confirming,
      confirmingPath,
      loadChunks,
      onKnowledgeBasesChanged,
      refreshHealth,
      resetChunks,
      setActionError,
      setHealth,
    ],
  )

  const isConfirming = useCallback(
    (path?: string) => confirming && confirmingPath === getKnowledgeBaseDeleteTargetPath(path),
    [confirming, confirmingPath],
  )

  return {
    deleting,
    deleteKnowledgeBase,
    isConfirming,
  }
}
