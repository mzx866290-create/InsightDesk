import React from 'react'

import type { SecurityAuditSummary } from '../../api/client'
import { SecurityAuditKpiItem } from './SecurityAuditKpiItem'

export interface SecurityAuditSummaryKpiPanelProps {
  activeCategoryCount: number
  activeCategoryLabel: string
  summary: SecurityAuditSummary | null
}

export const SecurityAuditSummaryKpiPanel: React.FC<SecurityAuditSummaryKpiPanelProps> = ({
  activeCategoryCount,
  activeCategoryLabel,
  summary,
}) => (
  <div className="grid gap-2 rounded-lg border border-bg-border bg-bg-tertiary/30 p-3 text-xs text-text-secondary sm:grid-cols-2 lg:grid-cols-5">
    <SecurityAuditKpiItem label="Category" value={activeCategoryLabel} />
    <SecurityAuditKpiItem label="Total" value={summary?.total ?? '-'} />
    <SecurityAuditKpiItem label="Recent / window" value={summary ? `${summary.recent_count} / ${summary.window_limit}` : '-'} />
    <SecurityAuditKpiItem label="Active categories" value={activeCategoryCount} />
    <SecurityAuditKpiItem
      label="Unknown actions"
      value={summary?.unknown_action_count ?? '-'}
      tone={summary && summary.unknown_action_count > 0 ? 'red' : 'default'}
    />
  </div>
)
