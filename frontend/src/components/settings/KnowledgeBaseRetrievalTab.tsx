import React, { useState } from 'react'
import {
  testKBRetrieval,
  type RetrievalTestResult,
} from '../../api/client'
import { isAdminAccessError } from '../admin/adminAccess'
import { KbRetrievalControls, type KbRetrievalMode } from './KbRetrievalControls'
import { KbRetrievalResultPanel } from './KbRetrievalResultPanel'

interface KnowledgeBaseRetrievalTabProps {
  onAdminAccessError?: (message: string | null) => void
}

export const KnowledgeBaseRetrievalTab: React.FC<KnowledgeBaseRetrievalTabProps> = ({
  onAdminAccessError,
}) => {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<RetrievalTestResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [retrievalMode, setRetrievalMode] = useState<KbRetrievalMode>('semantic')
  const [useRerank, setUseRerank] = useState(false)
  const [searchK, setSearchK] = useState(5)
  const [fetchK, setFetchK] = useState(10)

  const handleTest = async () => {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await testKBRetrieval(query.trim(), {
        retrieval_mode: retrievalMode,
        search_k: searchK,
        fetch_k: fetchK,
        use_rerank: useRerank,
      })
      setResult(res)
      if (res.error) setError(res.error)
      onAdminAccessError?.(null)
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : '检索失败'
      setError(message)
      if (isAdminAccessError(e)) onAdminAccessError?.(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <KbRetrievalControls
        variant="tab"
        query={query}
        loading={loading}
        mode={retrievalMode}
        searchK={searchK}
        fetchK={fetchK}
        useRerank={useRerank}
        onQueryChange={setQuery}
        onModeChange={setRetrievalMode}
        onSearchKChange={setSearchK}
        onFetchKChange={setFetchK}
        onUseRerankChange={setUseRerank}
        onTest={handleTest}
      />

      <KbRetrievalResultPanel
        variant="tab"
        result={result}
        error={error}
        showEmptyState
        showNoResultsState
      />
    </div>
  )
}
