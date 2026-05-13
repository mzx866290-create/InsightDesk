import { useState } from 'react'

import type { SecurityAuditSummaryCategory } from '../../api/client'
import type { SecurityAuditCountPanelsProps } from './SecurityAuditCountPanels'
import type { SecurityAuditEventsPanelProps } from './SecurityAuditEventsPanel'
import type { SecurityAuditStatusPanelProps } from './SecurityAuditStatusPanel'
import type { SecurityAuditSummaryKpiPanelProps } from './SecurityAuditSummaryKpiPanel'
import type { SecurityAuditToolbarProps } from './SecurityAuditToolbar'
import {
  activeSecurityAuditCategoryCount,
  activeSecurityAuditCategoryLabel,
  securityAuditResultOptions,
} from './securityAuditSummaryModel'
import { useSecurityAuditEventsController } from './useSecurityAuditEventsController'
import { useSecurityAuditSummaryData } from './useSecurityAuditSummaryData'

export interface UseSecurityAuditSummaryControllerResult {
  toolbarProps: SecurityAuditToolbarProps
  statusPanelProps: SecurityAuditStatusPanelProps
  kpiPanelProps: SecurityAuditSummaryKpiPanelProps
  countPanelProps: SecurityAuditCountPanelsProps
  eventsPanelProps: SecurityAuditEventsPanelProps
  securityStatusError: string | null
  summaryError: string | null
  showInitialSummaryLoading: boolean
}

export function useSecurityAuditSummaryController(): UseSecurityAuditSummaryControllerResult {
  const [category, setCategory] = useState<SecurityAuditSummaryCategory>('all')
  const [limit, setLimit] = useState<number>(200)
  const summaryData = useSecurityAuditSummaryData({ category, limit })
  const activeCategoryLabel = activeSecurityAuditCategoryLabel(category)
  const activeCategoryCount = activeSecurityAuditCategoryCount(summaryData.summary)
  const resultOptions = securityAuditResultOptions(summaryData.summary)

  const securityAuditEvents = useSecurityAuditEventsController({
    limit,
    onSummaryRefresh: summaryData.loadSummary,
    resultOptions,
  })

  return {
    toolbarProps: {
      category,
      limit,
      loading: summaryData.loading,
      onCategoryChange: setCategory,
      onLimitChange: setLimit,
      onRefresh: summaryData.refreshSummaryAndStatus,
    },
    statusPanelProps: {
      securityStatus: summaryData.securityStatus,
    },
    kpiPanelProps: {
      activeCategoryCount,
      activeCategoryLabel,
      summary: summaryData.summary,
    },
    countPanelProps: {
      summary: summaryData.summary,
      selectedAction: securityAuditEvents.selectedAction,
      onSelectAction: securityAuditEvents.onSelectAction,
    },
    eventsPanelProps: securityAuditEvents.eventsPanelProps,
    securityStatusError: summaryData.securityStatusError,
    summaryError: summaryData.summaryError,
    showInitialSummaryLoading: summaryData.loading && !summaryData.summary,
  }
}
