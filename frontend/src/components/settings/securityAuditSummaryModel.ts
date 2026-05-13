import type {
  SecurityAuditCleanupResponse,
  SecurityAuditEvent,
  SecurityAuditEventFilters,
  SecurityAuditSummary,
  SecurityAuditSummaryCategory,
} from '../../api/client'

export type CountKind = 'action' | 'result' | 'category'

export const SECURITY_AUDIT_CATEGORY_OPTIONS: Array<{ value: SecurityAuditSummaryCategory; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'access', label: 'Access' },
  { value: 'identity', label: 'Identity' },
  { value: 'auth', label: 'Auth' },
  { value: 'audit', label: 'Audit' },
]

export const SECURITY_AUDIT_LIMIT_OPTIONS = [50, 100, 200, 500] as const

export const SECURITY_AUDIT_EVENT_CATEGORY_FILTER_OPTIONS = SECURITY_AUDIT_CATEGORY_OPTIONS.filter(
  (option) => option.value !== 'all',
)

export function normalizeError(error: unknown, fallback = 'Failed to load security audit summary'): string {
  return error instanceof Error ? error.message : String(error || fallback)
}

export function sortedCountEntries(counts: Record<string, number>): Array<[string, number]> {
  return Object.entries(counts)
    .filter(([, count]) => Number.isFinite(count) && count > 0)
    .sort(([leftName, leftCount], [rightName, rightCount]) => {
      if (rightCount !== leftCount) return rightCount - leftCount
      return leftName.localeCompare(rightName)
    })
}

export function activeSecurityAuditCategoryLabel(category: SecurityAuditSummaryCategory): string {
  return SECURITY_AUDIT_CATEGORY_OPTIONS.find((option) => option.value === category)?.label ?? 'All'
}

export function activeSecurityAuditCategoryCount(summary: SecurityAuditSummary | null): number {
  return sortedCountEntries(summary?.category_counts ?? {}).length
}

export function securityAuditResultOptions(summary: SecurityAuditSummary | null): string[] {
  const names = sortedCountEntries(summary?.result_counts ?? {}).map(([name]) => name)
  return Array.from(new Set(names))
}

export function formatCountName(name: string): string {
  return name.trim() || 'unknown'
}

export function clampText(value: string, limit = 140): string {
  return value.length > limit ? `${value.slice(0, limit - 1)}...` : value
}

export function formatTimestamp(timestamp: number): string {
  if (!Number.isFinite(timestamp)) return '-'
  return new Date(timestamp * 1000).toLocaleString('zh-CN', { hour12: false })
}

export function parseDatetimeLocalSeconds(value: string): number | undefined {
  if (!value.trim()) return undefined
  const timestamp = new Date(value).getTime()
  if (!Number.isFinite(timestamp)) return undefined
  return Math.floor(timestamp / 1000)
}

export function formatRetentionCount(value: unknown): string {
  return typeof value === 'number' && Number.isFinite(value) ? String(value) : '-'
}

export function parseRetentionKeepLatest(value: string): number {
  return Math.max(0, Math.floor(Number(value) || 0))
}

export function buildRetentionPreview(
  eventsTotal: number,
  keepLatest: number,
): SecurityAuditCleanupResponse {
  return {
    keep_latest: keepLatest,
    would_delete_count: Math.max(0, eventsTotal - keepLatest),
    remaining_count: Math.min(eventsTotal, keepLatest),
    dry_run: true,
  }
}

export function formatDetailValue(value: unknown): string {
  if (value === null) return 'null'
  if (typeof value === 'string') return value.trim() || '""'
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

export function formatDetails(details: SecurityAuditEvent['details']): string {
  if (typeof details === 'string') return details.trim() || '-'
  if (!details || typeof details !== 'object') return '-'
  const entries = Object.entries(details)
  if (entries.length === 0) return '-'
  return entries
    .slice(0, 8)
    .map(([key, value]) => `${key}=${formatDetailValue(value)}`)
    .join(' | ')
}

export function resultBadgeClass(result: string): string {
  const normalized = result.toLowerCase()
  if (['ok', 'allowed', 'success'].includes(normalized)) {
    return 'bg-accent-green/15 text-accent-green'
  }
  if (
    normalized.includes('reject') ||
    normalized.includes('block') ||
    normalized.includes('deny') ||
    normalized.includes('fail') ||
    normalized.includes('error')
  ) {
    return 'bg-accent-red/15 text-accent-red'
  }
  return 'bg-bg-hover text-text-primary'
}

export function compactAuditEventFilters(filters: SecurityAuditEventFilters): SecurityAuditEventFilters {
  const since = typeof filters.since === 'number' && Number.isFinite(filters.since)
    ? Math.floor(filters.since)
    : undefined
  const until = typeof filters.until === 'number' && Number.isFinite(filters.until)
    ? Math.floor(filters.until)
    : undefined

  return {
    action: filters.action?.trim() || '',
    result: filters.result?.trim() || '',
    category: filters.category?.trim() || '',
    user_id: filters.user_id?.trim() || '',
    since,
    until,
  }
}

export function hasAuditEventFilters(filters: SecurityAuditEventFilters): boolean {
  const compact = compactAuditEventFilters(filters)
  return Boolean(compact.action || compact.result || compact.category || compact.user_id || compact.since || compact.until)
}

export function barClass(kind: CountKind, name: string): string {
  const normalized = name.toLowerCase()
  if (kind === 'result' && ['ok', 'allowed', 'success'].includes(normalized)) {
    return 'bg-accent-green'
  }
  if (
    kind === 'result' &&
    (normalized.includes('reject') ||
      normalized.includes('block') ||
      normalized.includes('deny') ||
      normalized.includes('fail') ||
      normalized.includes('error'))
  ) {
    return 'bg-accent-red'
  }
  if (kind === 'category') return 'bg-amber-300'
  return 'bg-accent-blue'
}

export function valueClass(kind: CountKind, name: string): string {
  const normalized = name.toLowerCase()
  if (kind === 'result' && ['ok', 'allowed', 'success'].includes(normalized)) {
    return 'text-accent-green'
  }
  if (
    kind === 'result' &&
    (normalized.includes('reject') ||
      normalized.includes('block') ||
      normalized.includes('deny') ||
      normalized.includes('fail') ||
      normalized.includes('error'))
  ) {
    return 'text-accent-red'
  }
  return 'text-text-primary'
}
