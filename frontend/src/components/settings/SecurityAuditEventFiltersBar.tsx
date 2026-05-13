import React from 'react'
import { RefreshCw, Search, X } from 'lucide-react'

import { Button } from '../ui/Button'
import {
  SECURITY_AUDIT_EVENT_CATEGORY_FILTER_OPTIONS,
  formatCountName,
} from './securityAuditSummaryModel'

export interface SecurityAuditEventFiltersBarProps {
  eventsCount: number
  eventsTotal: number
  eventsLimit: number
  actionFilter: string
  resultFilter: string
  categoryFilter: string
  userFilter: string
  sinceFilter: string
  untilFilter: string
  resultOptions: string[]
  loading: boolean
  resetDisabled: boolean
  onActionFilterChange: (value: string) => void
  onResultFilterChange: (value: string) => void
  onCategoryFilterChange: (value: string) => void
  onUserFilterChange: (value: string) => void
  onSinceFilterChange: (value: string) => void
  onUntilFilterChange: (value: string) => void
  onApplyFilters: () => void
  onResetFilters: () => void
  onRefresh: () => void
}

export const SecurityAuditEventFiltersBar: React.FC<SecurityAuditEventFiltersBarProps> = ({
  eventsCount,
  eventsTotal,
  eventsLimit,
  actionFilter,
  resultFilter,
  categoryFilter,
  userFilter,
  sinceFilter,
  untilFilter,
  resultOptions,
  loading,
  resetDisabled,
  onActionFilterChange,
  onResultFilterChange,
  onCategoryFilterChange,
  onUserFilterChange,
  onSinceFilterChange,
  onUntilFilterChange,
  onApplyFilters,
  onResetFilters,
  onRefresh,
}) => (
  <div
    className="flex flex-wrap items-center justify-between gap-2 border-b border-bg-border bg-bg-tertiary/60 px-3 py-2"
    data-testid="settings-security-audit-event-filters"
  >
    <div className="text-[11px] font-medium uppercase tracking-wide text-text-secondary">
      Events{' '}
      <span className="normal-case tracking-normal">
        ({eventsCount} / {eventsTotal}, limit {eventsLimit})
      </span>
    </div>
    <div className="flex flex-wrap items-center gap-2">
      <input
        className="input-base w-56 max-w-full py-1 font-mono text-xs"
        placeholder="action"
        value={actionFilter}
        onChange={(event) => onActionFilterChange(event.target.value)}
        onKeyDown={(event) => event.key === 'Enter' && onApplyFilters()}
        data-testid="settings-security-audit-event-action-filter"
      />
      <select
        className="input-base py-1 text-xs"
        value={resultFilter}
        onChange={(event) => onResultFilterChange(event.target.value)}
        data-testid="settings-security-audit-event-result-filter"
      >
        <option value="">All results</option>
        {resultOptions.map((name) => (
          <option key={name} value={name}>
            {formatCountName(name)}
          </option>
        ))}
      </select>
      <select
        className="input-base py-1 text-xs"
        value={categoryFilter}
        onChange={(event) => onCategoryFilterChange(event.target.value)}
        data-testid="settings-security-audit-event-category-filter"
      >
        <option value="">All categories</option>
        {SECURITY_AUDIT_EVENT_CATEGORY_FILTER_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <input
        className="input-base w-40 max-w-full py-1 font-mono text-xs"
        placeholder="user id"
        value={userFilter}
        onChange={(event) => onUserFilterChange(event.target.value)}
        onKeyDown={(event) => event.key === 'Enter' && onApplyFilters()}
        data-testid="settings-security-audit-event-user-filter"
      />
      <input
        className="input-base w-44 max-w-full py-1 text-xs"
        type="datetime-local"
        value={sinceFilter}
        onChange={(event) => onSinceFilterChange(event.target.value)}
        data-testid="settings-security-audit-event-since-filter"
      />
      <input
        className="input-base w-44 max-w-full py-1 text-xs"
        type="datetime-local"
        value={untilFilter}
        onChange={(event) => onUntilFilterChange(event.target.value)}
        data-testid="settings-security-audit-event-until-filter"
      />
      <Button
        variant="primary"
        size="sm"
        onClick={onApplyFilters}
        loading={loading}
        data-testid="settings-security-audit-event-apply-filters"
      >
        <Search size={12} />
        Filter
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={onResetFilters}
        disabled={resetDisabled}
        data-testid="settings-security-audit-event-reset-filters"
      >
        <X size={12} />
        Reset
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={onRefresh}
        loading={loading}
        data-testid="settings-security-audit-event-refresh"
      >
        <RefreshCw size={12} />
        Refresh
      </Button>
    </div>
  </div>
)
