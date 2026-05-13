import React from 'react'

import { SecurityAuditEventsPanel } from './SecurityAuditEventsPanel'
import { SecurityAuditStatusPanel } from './SecurityAuditStatusPanel'
import { SecurityAuditSummaryKpiPanel } from './SecurityAuditSummaryKpiPanel'
import { SecurityAuditToolbar } from './SecurityAuditToolbar'
import { SecurityAuditCountPanels } from './SecurityAuditCountPanels'
import { SecurityAuditErrorNotice } from './SecurityAuditErrorNotice'
import { useSecurityAuditSummaryController } from './useSecurityAuditSummaryController'

export const SecurityAuditSummaryPanel: React.FC = () => {
  const {
    toolbarProps,
    statusPanelProps,
    kpiPanelProps,
    countPanelProps,
    eventsPanelProps,
    securityStatusError,
    summaryError,
    showInitialSummaryLoading,
  } = useSecurityAuditSummaryController()

  return (
    <div className="space-y-4" data-testid="settings-security-audit-summary-panel">
      <SecurityAuditToolbar {...toolbarProps} />

      <SecurityAuditStatusPanel {...statusPanelProps} />

      {securityStatusError && (
        <SecurityAuditErrorNotice testId="settings-security-status-error" message={securityStatusError} />
      )}

      <SecurityAuditSummaryKpiPanel {...kpiPanelProps} />

      {summaryError && (
        <SecurityAuditErrorNotice testId="settings-security-audit-error" message={summaryError} />
      )}

      {showInitialSummaryLoading && (
        <div className="flex justify-center rounded-lg border border-bg-border py-8">
          <span className="h-5 w-5 animate-spin rounded-full border-2 border-accent-blue border-t-transparent" />
        </div>
      )}

      <SecurityAuditCountPanels {...countPanelProps} />

      <SecurityAuditEventsPanel {...eventsPanelProps} />
    </div>
  )
}
