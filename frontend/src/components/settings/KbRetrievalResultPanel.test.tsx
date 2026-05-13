import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { RetrievalDebugItem, RetrievalTestResult } from '../../api/client'
import { KbRetrievalResultPanel } from './KbRetrievalResultPanel'

const candidate = (patch: Partial<RetrievalDebugItem> = {}): RetrievalDebugItem => ({
  rank: 1,
  source: 'docs/retrieval.md',
  snippet: 'Matched retrieval content',
  score: 0.91,
  channel: 'semantic',
  matched_terms: ['retrieval'],
  ...patch,
})

const result = (patch: Partial<RetrievalTestResult> = {}): RetrievalTestResult => ({
  results_count: 1,
  latency_ms: 24,
  search_mode: 'hybrid_rerank',
  coverage: {
    unique_sources: 1,
    source_ratio: 1,
    matched_terms: ['retrieval'],
    matched_term_count: 1,
  },
  rewrite_query: 'rewritten query',
  top_results: [candidate()],
  semantic_candidates: [candidate({ source: 'docs/semantic.md', channel: 'semantic' })],
  keyword_candidates: [candidate({ source: 'docs/keyword.md', channel: 'keyword' })],
  fused_candidates: [candidate({ source: 'docs/fused.md', channel: 'fused' })],
  ...patch,
})

describe('KbRetrievalResultPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders diagnostic result summary and reuses debug lists', () => {
    render(
      <KbRetrievalResultPanel
        result={result()}
        testIdPrefix="settings-kb-retrieval"
      />,
    )

    expect(screen.getByTestId('settings-kb-retrieval-result')).toBeInTheDocument()
    expect(screen.getByTestId('settings-kb-retrieval-results-count')).toHaveTextContent('1')
    expect(screen.getByText('hybrid_rerank')).toHaveClass('text-accent-green')
    expect(screen.getByText('rewritten query')).toBeInTheDocument()
    expect(screen.getByText('docs/retrieval.md')).toBeInTheDocument()
    expect(screen.getByText('docs/semantic.md')).toBeInTheDocument()
    expect(screen.getByText('docs/keyword.md')).toBeInTheDocument()
    expect(screen.getByText('docs/fused.md')).toBeInTheDocument()
  })

  it('renders diagnostic API errors inside the result container', () => {
    render(
      <KbRetrievalResultPanel
        result={result({ error: 'retrieval failed' })}
        testIdPrefix="settings-kb-retrieval"
      />,
    )

    expect(screen.getByTestId('settings-kb-retrieval-result')).toBeInTheDocument()
    expect(screen.getByTestId('settings-kb-retrieval-error')).toHaveTextContent('retrieval failed')
  })

  it('renders tab error, empty and no-result states by test id', () => {
    const { rerender } = render(
      <KbRetrievalResultPanel
        variant="tab"
        result={null}
        error="request failed"
        testIdPrefix="kb-tab"
      />,
    )

    expect(screen.getByTestId('kb-tab-error')).toHaveTextContent('request failed')

    rerender(
      <KbRetrievalResultPanel
        variant="tab"
        result={null}
        showEmptyState
        testIdPrefix="kb-tab"
      />,
    )

    expect(screen.getByTestId('kb-tab-empty')).toBeInTheDocument()

    rerender(
      <KbRetrievalResultPanel
        variant="tab"
        result={result({ top_results: [] })}
        showNoResultsState
        testIdPrefix="kb-tab"
      />,
    )

    expect(screen.getByTestId('kb-tab-no-results')).toBeInTheDocument()
  })
})
