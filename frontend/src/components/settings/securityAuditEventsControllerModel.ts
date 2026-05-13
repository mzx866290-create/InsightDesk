import {
  cleanupSecurityAuditEvents,
  getSecurityAuditEvents,
  type SecurityAuditCleanupResponse,
  type SecurityAuditEvent,
  type SecurityAuditEventFilters,
} from '../../api/client'
import type { SecurityAuditEventsPanelProps } from './SecurityAuditEventsPanel'
import {
  compactAuditEventFilters,
  normalizeError,
  parseDatetimeLocalSeconds,
} from './securityAuditSummaryModel'

export interface AuditEventFilterDraftValues {
  actionFilter: string
  resultFilter: string
  categoryFilter: string
  userFilter: string
  sinceFilter: string
  untilFilter: string
}

export interface LoadedSecurityAuditEventsState {
  events: SecurityAuditEvent[]
  total: number
  limit: number
}

export interface SecurityAuditEventsPanelState {
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
}

export type SecurityAuditEventsPanelHandlers = Pick<
  SecurityAuditEventsPanelProps,
  | 'onActionFilterChange'
  | 'onResultFilterChange'
  | 'onCategoryFilterChange'
  | 'onUserFilterChange'
  | 'onSinceFilterChange'
  | 'onUntilFilterChange'
  | 'onApplyFilters'
  | 'onResetFilters'
  | 'onRefresh'
  | 'onKeepLatestChange'
  | 'onPreviewRetention'
  | 'onCleanupRetention'
>

export function buildDraftAuditEventFilters({
  actionFilter,
  resultFilter,
  categoryFilter,
  userFilter,
  sinceFilter,
  untilFilter,
}: AuditEventFilterDraftValues): SecurityAuditEventFilters {
  return compactAuditEventFilters({
    action: actionFilter,
    result: resultFilter,
    category: categoryFilter,
    user_id: userFilter,
    since: parseDatetimeLocalSeconds(sinceFilter),
    until: parseDatetimeLocalSeconds(untilFilter),
  })
}

export async function loadSecurityAuditEventsState(
  limit: number,
  filters: SecurityAuditEventFilters,
): Promise<LoadedSecurityAuditEventsState> {
  const payload = await getSecurityAuditEvents(limit, compactAuditEventFilters(filters))

  return {
    events: payload.events,
    total: payload.total,
    limit: payload.limit,
  }
}

export interface CleanupSecurityAuditEventsStateOptions {
  keepLatest: number
  onSummaryRefresh: () => Promise<void>
}

export async function cleanupSecurityAuditEventsState({
  keepLatest,
  onSummaryRefresh,
}: CleanupSecurityAuditEventsStateOptions): Promise<SecurityAuditCleanupResponse> {
  const cleanup = await cleanupSecurityAuditEvents({ keep_latest: keepLatest })
  await onSummaryRefresh()
  return cleanup
}

export function normalizeAuditEventsLoadError(error: unknown): string {
  return normalizeError(error, 'Failed to load security audit events')
}

export function normalizeAuditEventsCleanupError(error: unknown): string {
  return normalizeError(error, 'Failed to cleanup security audit events')
}

export function createSecurityAuditEventsPanelProps(
  state: SecurityAuditEventsPanelState,
  handlers: SecurityAuditEventsPanelHandlers,
): SecurityAuditEventsPanelProps {
  return {
    ...state,
    ...handlers,
  }
}
