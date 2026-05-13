import React from 'react'

import type { TraceSummary } from '../../api/client'

interface TraceOperationsSummaryProps {
  filtersActive: boolean
  latestTimestamp: string
  summary: TraceSummary
}

export const TraceOperationsSummary: React.FC<TraceOperationsSummaryProps> = ({
  filtersActive,
  latestTimestamp,
  summary,
}) => {
  return (
    <div
      className="grid gap-2 rounded-lg border border-bg-border bg-bg-tertiary/30 px-3 py-2 text-xs text-text-secondary sm:grid-cols-4"
      data-testid="settings-trace-summary"
    >
      <span>返回：<b className="text-text-primary">{summary.returned}</b> / {summary.limit}</span>
      <span>错误：<b className="text-accent-red">{summary.error_events}</b></span>
      <span>最新：<b className="text-text-primary">{latestTimestamp}</b></span>
      <span>筛选：<b className="text-text-primary" data-testid="settings-trace-filter-status">{filtersActive ? 'filtered' : 'all'}</b></span>
    </div>
  )
}
