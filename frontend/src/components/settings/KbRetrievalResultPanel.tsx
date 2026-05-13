import React from 'react'
import type { RetrievalTestResult } from '../../api/client'
import { KbRetrievalCandidateLists } from './KbRetrievalCandidateLists'
import {
  getKbRetrievalTestId,
  hasKbRetrievalTopResults,
  type KbRetrievalResultVariant,
} from './KbRetrievalResultModel'
import {
  KbRetrievalCoverageStats,
  KbRetrievalDiagnosticMeta,
  KbRetrievalRewriteSummary,
  KbRetrievalTabMeta,
} from './KbRetrievalResultSections'

interface KbRetrievalResultPanelProps {
  result: RetrievalTestResult | null
  error?: string | null
  variant?: KbRetrievalResultVariant
  showEmptyState?: boolean
  showNoResultsState?: boolean
  testIdPrefix?: string
}

function KbRetrievalDiagnosticResult({
  result,
  testIdPrefix,
}: {
  result: RetrievalTestResult
  testIdPrefix?: string
}) {
  return (
    <div
      className="mt-3 bg-bg-tertiary rounded-lg p-3 space-y-2"
      data-testid={getKbRetrievalTestId(testIdPrefix, 'result')}
    >
      {result.error ? (
        <p className="text-xs text-accent-red" data-testid={getKbRetrievalTestId(testIdPrefix, 'error')}>
          {result.error}
        </p>
      ) : (
        <>
          <KbRetrievalDiagnosticMeta result={result} testIdPrefix={testIdPrefix} />
          {result.coverage && <KbRetrievalCoverageStats coverage={result.coverage} variant="diagnostic" />}
          {result.rewrite_query && <KbRetrievalRewriteSummary query={result.rewrite_query} variant="diagnostic" />}
          <KbRetrievalCandidateLists result={result} variant="diagnostic" />
        </>
      )}
    </div>
  )
}

function KbRetrievalTabResult({
  result,
  showNoResultsState,
  testIdPrefix,
}: {
  result: RetrievalTestResult
  showNoResultsState: boolean
  testIdPrefix?: string
}) {
  const hasTopResults = hasKbRetrievalTopResults(result)

  return (
    <div className="space-y-3">
      <KbRetrievalTabMeta result={result} />
      {result.coverage && <KbRetrievalCoverageStats coverage={result.coverage} variant="tab" />}
      {result.rewrite_query && <KbRetrievalRewriteSummary query={result.rewrite_query} variant="tab" />}

      {hasTopResults ? (
        <KbRetrievalCandidateLists result={result} variant="tab" />
      ) : (
        showNoResultsState && (
          <p
            className="text-sm text-center text-text-secondary py-4"
            data-testid={getKbRetrievalTestId(testIdPrefix, 'no-results')}
          >
            未命中任何片段
          </p>
        )
      )}
    </div>
  )
}

export function KbRetrievalResultPanel({
  result,
  error,
  variant = 'diagnostic',
  showEmptyState = false,
  showNoResultsState = false,
  testIdPrefix,
}: KbRetrievalResultPanelProps) {
  if (error) {
    return (
      <div
        className="px-3 py-2 bg-accent-red/10 border border-accent-red/20 rounded-lg text-xs text-accent-red"
        data-testid={getKbRetrievalTestId(testIdPrefix, 'error')}
      >
        {error}
      </div>
    )
  }

  if (!result) {
    if (!showEmptyState) return null

    return (
      <div
        className="text-center py-8 text-text-muted text-sm"
        data-testid={getKbRetrievalTestId(testIdPrefix, 'empty')}
      >
        输入查询词后点击检索，查看知识库召回效果和命中片段
      </div>
    )
  }

  if (variant === 'tab') {
    return (
      <KbRetrievalTabResult
        result={result}
        showNoResultsState={showNoResultsState}
        testIdPrefix={testIdPrefix}
      />
    )
  }

  return <KbRetrievalDiagnosticResult result={result} testIdPrefix={testIdPrefix} />
}
