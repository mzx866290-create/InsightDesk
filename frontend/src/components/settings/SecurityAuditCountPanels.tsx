import React from 'react'

import type { SecurityAuditSummary } from '../../api/client'
import { SecurityAuditCountList } from './SecurityAuditCountList'

export interface SecurityAuditCountPanelsProps {
  summary: SecurityAuditSummary | null
  selectedAction?: string
  onSelectAction: (action: string) => void
}

export const SecurityAuditCountPanels: React.FC<SecurityAuditCountPanelsProps> = ({
  summary,
  selectedAction,
  onSelectAction,
}) => {
  if (!summary) {
    return null
  }

  return (
    <div className="grid gap-3 lg:grid-cols-3">
      <SecurityAuditCountList
        title="Actions"
        counts={summary.action_counts}
        kind="action"
        emptyText="No actions in this window."
        mono
        testId="settings-security-audit-actions"
        selectedName={selectedAction}
        onSelectName={onSelectAction}
      />
      <SecurityAuditCountList
        title="Results"
        counts={summary.result_counts}
        kind="result"
        emptyText="No results in this window."
        testId="settings-security-audit-results"
      />
      <SecurityAuditCountList
        title="Categories"
        counts={summary.category_counts}
        kind="category"
        emptyText="No categories in this window."
        testId="settings-security-audit-categories"
      />
    </div>
  )
}
