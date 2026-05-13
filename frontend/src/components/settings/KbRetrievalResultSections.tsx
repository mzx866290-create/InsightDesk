import React from 'react'
import type { RetrievalTestResult } from '../../api/client'
import {
  getKbRetrievalSearchModeClassName,
  getKbRetrievalTestId,
} from './KbRetrievalResultModel'

type KbRetrievalCoverage = NonNullable<RetrievalTestResult['coverage']>

interface KbRetrievalDiagnosticMetaProps {
  result: RetrievalTestResult
  testIdPrefix?: string
}

export function KbRetrievalDiagnosticMeta({
  result,
  testIdPrefix,
}: KbRetrievalDiagnosticMetaProps) {
  return (
    <div className="flex flex-wrap gap-3 text-xs">
      <span className="text-text-secondary">
        命中数：
        <span
          className="text-text-primary font-medium"
          data-testid={getKbRetrievalTestId(testIdPrefix, 'results-count')}
        >
          {result.results_count}
        </span>
      </span>
      <span className="text-text-secondary">
        延迟：<span className="text-text-primary font-medium">{result.latency_ms} ms</span>
      </span>
      {result.search_mode && (
        <span className={`rounded-full px-2 py-0.5 font-medium ${getKbRetrievalSearchModeClassName(result.search_mode)}`}>
          {result.search_mode}
        </span>
      )}
    </div>
  )
}

export function KbRetrievalTabMeta({ result }: { result: RetrievalTestResult }) {
  return (
    <div className="flex items-center gap-4 px-3 py-2 bg-bg-tertiary rounded-lg border border-bg-border">
      <div className="text-center">
        <div className="text-lg font-bold text-text-primary">{result.results_count}</div>
        <div className="text-[10px] text-text-muted">命中数</div>
      </div>
      <div className="text-center">
        <div className="text-lg font-bold text-accent-green">{result.latency_ms}ms</div>
        <div className="text-[10px] text-text-muted">耗时</div>
      </div>
      {result.search_mode && (
        <div className="ml-auto text-right">
          <div className="text-sm font-semibold text-text-primary">{result.search_mode}</div>
          <div className="text-[10px] text-text-muted">执行模式</div>
        </div>
      )}
    </div>
  )
}

export function KbRetrievalCoverageStats({
  coverage,
  variant,
}: {
  coverage: KbRetrievalCoverage
  variant: 'diagnostic' | 'tab'
}) {
  if (variant === 'diagnostic') {
    return (
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div className="rounded-md bg-bg-secondary/60 p-2 text-text-secondary/80">
          唯一来源数：<span className="font-medium text-text-primary">{coverage.unique_sources}</span>
        </div>
        <div className="rounded-md bg-bg-secondary/60 p-2 text-text-secondary/80">
          命中词数：<span className="font-medium text-text-primary">{coverage.matched_term_count}</span>
        </div>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 gap-2 text-xs">
      <div className="rounded-lg border border-bg-border bg-bg-secondary/40 px-3 py-2">
        <div className="text-text-muted">去重来源</div>
        <div className="text-text-primary font-semibold">{coverage.unique_sources}</div>
      </div>
      <div className="rounded-lg border border-bg-border bg-bg-secondary/40 px-3 py-2">
        <div className="text-text-muted">命中关键词</div>
        <div className="text-text-primary font-semibold">{coverage.matched_term_count}</div>
      </div>
    </div>
  )
}

export function KbRetrievalRewriteSummary({
  query,
  variant,
}: {
  query: string
  variant: 'diagnostic' | 'tab'
}) {
  if (variant === 'diagnostic') {
    return (
      <div className="rounded-md bg-bg-secondary/60 p-2 text-[11px] text-text-secondary/80">
        实际查询：<span className="text-text-primary">{query}</span>
      </div>
    )
  }

  return (
    <div className="px-3 py-2 rounded-lg border border-bg-border bg-bg-secondary/40">
      <div className="text-[10px] uppercase tracking-wide text-text-muted mb-1">Effective Query</div>
      <div className="text-sm text-text-primary">{query}</div>
    </div>
  )
}
