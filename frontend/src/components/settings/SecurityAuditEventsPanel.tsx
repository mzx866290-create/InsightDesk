import React from 'react'
import { AlertTriangle } from 'lucide-react'

import type {
  SecurityAuditCleanupResponse,
  SecurityAuditEvent,
} from '../../api/client'
import { SecurityAuditEventFiltersBar } from './SecurityAuditEventFiltersBar'
import { SecurityAuditEventsTable } from './SecurityAuditEventsTable'
import { SecurityAuditRetentionBar } from './SecurityAuditRetentionBar'

export interface SecurityAuditEventsPanelProps {
  events: SecurityAuditEvent[]
  eventsTotal: number
  eventsLimit: number
  eventsLoading: boolean
  eventsError: string | null
  actionFilter: string
  resultFilter: string
  categoryFilter: string
  userFilter: string
  sinceFilter: string
  untilFilter: string
  resultOptions: string[]
  resetDisabled: boolean
  retentionKeepLatest: string
  retentionLoading: 'preview' | 'cleanup' | null
  retentionResult: SecurityAuditCleanupResponse | null
  retentionError: string | null
  onActionFilterChange: (value: string) => void
  onResultFilterChange: (value: string) => void
  onCategoryFilterChange: (value: string) => void
  onUserFilterChange: (value: string) => void
  onSinceFilterChange: (value: string) => void
  onUntilFilterChange: (value: string) => void
  onApplyFilters: () => void
  onResetFilters: () => void
  onRefresh: () => void
  onKeepLatestChange: (value: string) => void
  onPreviewRetention: () => void
  onCleanupRetention: () => void
}

export const SecurityAuditEventsPanel: React.FC<SecurityAuditEventsPanelProps> = ({
  events,
  eventsTotal,
  eventsLimit,
  eventsLoading,
  eventsError,
  actionFilter,
  resultFilter,
  categoryFilter,
  userFilter,
  sinceFilter,
  untilFilter,
  resultOptions,
  resetDisabled,
  retentionKeepLatest,
  retentionLoading,
  retentionResult,
  retentionError,
  onActionFilterChange,
  onResultFilterChange,
  onCategoryFilterChange,
  onUserFilterChange,
  onSinceFilterChange,
  onUntilFilterChange,
  onApplyFilters,
  onResetFilters,
  onRefresh,
  onKeepLatestChange,
  onPreviewRetention,
  onCleanupRetention,
}) => (
  <div className="overflow-hidden rounded-lg border border-bg-border" data-testid="settings-security-audit-events">
    <SecurityAuditEventFiltersBar
      eventsCount={events.length}
      eventsTotal={eventsTotal}
      eventsLimit={eventsLimit}
      actionFilter={actionFilter}
      resultFilter={resultFilter}
      categoryFilter={categoryFilter}
      userFilter={userFilter}
      sinceFilter={sinceFilter}
      untilFilter={untilFilter}
      resultOptions={resultOptions}
      loading={eventsLoading}
      resetDisabled={resetDisabled}
      onActionFilterChange={onActionFilterChange}
      onResultFilterChange={onResultFilterChange}
      onCategoryFilterChange={onCategoryFilterChange}
      onUserFilterChange={onUserFilterChange}
      onSinceFilterChange={onSinceFilterChange}
      onUntilFilterChange={onUntilFilterChange}
      onApplyFilters={onApplyFilters}
      onResetFilters={onResetFilters}
      onRefresh={onRefresh}
    />

    {eventsError && (
      <div
        className="flex items-start gap-2 border-b border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red"
        data-testid="settings-security-audit-event-error"
      >
        <AlertTriangle size={13} className="mt-0.5 shrink-0" />
        <span>{eventsError}</span>
      </div>
    )}

    <SecurityAuditRetentionBar
      keepLatest={retentionKeepLatest}
      loading={retentionLoading}
      result={retentionResult}
      error={retentionError}
      onKeepLatestChange={onKeepLatestChange}
      onPreview={onPreviewRetention}
      onCleanup={onCleanupRetention}
    />

    <SecurityAuditEventsTable events={events} loading={eventsLoading} />
  </div>
)
