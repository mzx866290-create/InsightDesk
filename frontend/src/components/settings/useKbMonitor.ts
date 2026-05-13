import { useCallback, useEffect, useMemo, useState } from 'react'

import type { KBHealthData } from '../../api/client'
import type { KbChunkBrowserProps } from './KbChunkBrowser'
import type { KbDangerZoneProps } from './KbDangerZone'
import type { KbRetrievalMode, KbRetrievalTestPanelProps } from './KbRetrievalTestPanel'
import type { DeleteKnowledgeBaseResult } from './kbMonitorModel'
import { useKbChunkBrowserController } from './useKbChunkBrowserController'
import {
  useKbHealthLoader,
  useKbRetrievalTestActions,
  useKnowledgeBaseDeleteAction,
} from './useKbMonitorActions'

interface UseKbMonitorOptions {
  enabled: boolean
  onKnowledgeBasesChanged: () => Promise<void> | void
}

export interface KbMonitorController {
  health: KBHealthData | null
  loadingHealth: boolean
  actionError: string | null
  chunkBrowserProps: KbChunkBrowserProps
  retrievalTestProps: KbRetrievalTestPanelProps
  dangerZoneProps: KbDangerZoneProps
  deletingKnowledgeBase: boolean
  isDeleteKnowledgeBaseConfirming: (path?: string) => boolean
  refreshHealth: () => Promise<void>
  refreshCurrent: () => Promise<void>
  deleteKnowledgeBase: (path?: string) => Promise<DeleteKnowledgeBaseResult>
}

export function useKbMonitor({
  enabled,
  onKnowledgeBasesChanged,
}: UseKbMonitorOptions): KbMonitorController {
  const [testQuery, setTestQuery] = useState('')
  const [retrievalMode, setRetrievalMode] = useState<KbRetrievalMode>('semantic')
  const [retrievalSearchK, setRetrievalSearchK] = useState(5)
  const [retrievalFetchK, setRetrievalFetchK] = useState(10)
  const [retrievalUseRerank, setRetrievalUseRerank] = useState(false)
  const {
    health,
    loadingHealth,
    actionError,
    refreshHealth,
    setActionError,
    setHealth,
  } = useKbHealthLoader()

  const {
    chunkBrowserProps,
    loadChunks,
    loadCurrentChunks,
    loadInitialChunks,
    resetChunks,
  } = useKbChunkBrowserController({
    healthDocuments: health?.documents,
    refreshHealth,
    setActionError,
  })

  const refreshCurrent = useCallback(async () => {
    await refreshHealth()
    await loadCurrentChunks()
  }, [loadCurrentChunks, refreshHealth])

  useEffect(() => {
    if (!enabled) return
    void refreshHealth()
    loadInitialChunks()
  }, [enabled, loadInitialChunks, refreshHealth])

  const retrievalSettings = useMemo(
    () => ({
      mode: retrievalMode,
      searchK: retrievalSearchK,
      fetchK: retrievalFetchK,
      useRerank: retrievalUseRerank,
    }),
    [retrievalFetchK, retrievalMode, retrievalSearchK, retrievalUseRerank],
  )

  const {
    result: testResult,
    loading: testingRetrieval,
    runTest: handleTestRetrieval,
  } = useKbRetrievalTestActions({
    query: testQuery,
    settings: retrievalSettings,
  })

  const {
    deleting: deletingKnowledgeBase,
    deleteKnowledgeBase: handleDeleteKnowledgeBase,
    isConfirming: isDeleteKnowledgeBaseConfirming,
  } = useKnowledgeBaseDeleteAction({
    loadChunks,
    onKnowledgeBasesChanged,
    refreshHealth,
    resetChunks,
    setActionError,
    setHealth,
  })

  const retrievalTestProps = useMemo<KbRetrievalTestPanelProps>(
    () => ({
      query: testQuery,
      result: testResult,
      loading: testingRetrieval,
      mode: retrievalMode,
      searchK: retrievalSearchK,
      fetchK: retrievalFetchK,
      useRerank: retrievalUseRerank,
      onQueryChange: setTestQuery,
      onModeChange: setRetrievalMode,
      onSearchKChange: setRetrievalSearchK,
      onFetchKChange: setRetrievalFetchK,
      onUseRerankChange: setRetrievalUseRerank,
      onTest: handleTestRetrieval,
    }),
    [
      handleTestRetrieval,
      retrievalFetchK,
      retrievalMode,
      retrievalSearchK,
      retrievalUseRerank,
      testQuery,
      testResult,
      testingRetrieval,
    ],
  )

  const dangerZoneProps = useMemo<KbDangerZoneProps>(
    () => ({
      deleting: deletingKnowledgeBase,
      confirming: isDeleteKnowledgeBaseConfirming(),
      onDelete: () => {
        void handleDeleteKnowledgeBase()
      },
    }),
    [deletingKnowledgeBase, handleDeleteKnowledgeBase, isDeleteKnowledgeBaseConfirming],
  )

  return {
    health,
    loadingHealth,
    actionError,
    chunkBrowserProps,
    retrievalTestProps,
    dangerZoneProps,
    deletingKnowledgeBase,
    isDeleteKnowledgeBaseConfirming,
    refreshHealth,
    refreshCurrent,
    deleteKnowledgeBase: handleDeleteKnowledgeBase,
  }
}
