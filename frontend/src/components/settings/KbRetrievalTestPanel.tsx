import React from 'react'
import { Zap } from 'lucide-react'
import type { RetrievalTestResult } from '../../api/client'
import { KbRetrievalControls, type KbRetrievalMode } from './KbRetrievalControls'
import { KbRetrievalResultPanel } from './KbRetrievalResultPanel'

export type { KbRetrievalMode } from './KbRetrievalControls'

export interface KbRetrievalTestPanelProps {
  query: string
  result: RetrievalTestResult | null
  loading: boolean
  mode: KbRetrievalMode
  searchK: number
  fetchK: number
  useRerank: boolean
  onQueryChange: (value: string) => void
  onModeChange: (value: KbRetrievalMode) => void
  onSearchKChange: (value: number) => void
  onFetchKChange: (value: number) => void
  onUseRerankChange: (value: boolean) => void
  onTest: () => void
}

export function KbRetrievalTestPanel({
  query,
  result,
  loading,
  mode,
  searchK,
  fetchK,
  useRerank,
  onQueryChange,
  onModeChange,
  onSearchKChange,
  onFetchKChange,
  onUseRerankChange,
  onTest,
}: KbRetrievalTestPanelProps) {
  return (
    <div className="border-t border-bg-border pt-4" data-testid="settings-kb-retrieval-panel">
      <h4 className="text-xs font-medium text-text-secondary uppercase tracking-wide mb-3 flex items-center gap-1.5">
        <Zap size={11} />
        检索诊断
      </h4>

      <KbRetrievalControls
        query={query}
        loading={loading}
        mode={mode}
        searchK={searchK}
        fetchK={fetchK}
        useRerank={useRerank}
        testIdPrefix="settings-kb-retrieval"
        onQueryChange={onQueryChange}
        onModeChange={onModeChange}
        onSearchKChange={onSearchKChange}
        onFetchKChange={onFetchKChange}
        onUseRerankChange={onUseRerankChange}
        onTest={onTest}
      />

      <KbRetrievalResultPanel
        result={result}
        testIdPrefix="settings-kb-retrieval"
      />
    </div>
  )
}
