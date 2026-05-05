import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  BarChart3,
  Layers3,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  X,
} from 'lucide-react'

import {
  cleanupSecurityAuditEvents,
  getSecurityAuditEvents,
  getSecurityAuditSummary,
} from '../../api/client'
import type {
  SecurityAuditCleanupResponse,
  SecurityAuditEvent,
  SecurityAuditEventFilters,
  SecurityAuditSummary,
  SecurityAuditSummaryCategory,
} from '../../api/client'
import { Button } from '../ui/Button'

const CATEGORY_OPTIONS: Array<{ value: SecurityAuditSummaryCategory; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'access', label: 'Access' },
  { value: 'identity', label: 'Identity' },
  { value: 'auth', label: 'Auth' },
  { value: 'audit', label: 'Audit' },
]

const LIMIT_OPTIONS = [50, 100, 200, 500] as const
const EVENT_CATEGORY_FILTER_OPTIONS = CATEGORY_OPTIONS.filter((option) => option.value !== 'all')

type CountKind = 'action' | 'result' | 'category'

interface KpiItemProps {
  label: string
  value: string | number
  tone?: 'default' | 'green' | 'red'
}

interface CountListProps {
  title: string
  counts: Record<string, number>
  kind: CountKind
  emptyText: string
  mono?: boolean
  testId: string
  selectedName?: string
  onSelectName?: (name: string) => void
}

function normalizeError(error: unknown, fallback = 'Failed to load security audit summary'): string {
  return error instanceof Error ? error.message : String(error || fallback)
}

function sortedCountEntries(counts: Record<string, number>): Array<[string, number]> {
  return Object.entries(counts)
    .filter(([, count]) => Number.isFinite(count) && count > 0)
    .sort(([leftName, leftCount], [rightName, rightCount]) => {
      if (rightCount !== leftCount) return rightCount - leftCount
      return leftName.localeCompare(rightName)
    })
}

function formatCountName(name: string): string {
  return name.trim() || 'unknown'
}

function clampText(value: string, limit = 140): string {
  return value.length > limit ? `${value.slice(0, limit - 1)}...` : value
}

function formatTimestamp(timestamp: number): string {
  if (!Number.isFinite(timestamp)) return '-'
  return new Date(timestamp * 1000).toLocaleString('zh-CN', { hour12: false })
}

function parseDatetimeLocalSeconds(value: string): number | undefined {
  if (!value.trim()) return undefined
  const timestamp = new Date(value).getTime()
  if (!Number.isFinite(timestamp)) return undefined
  return Math.floor(timestamp / 1000)
}

function formatRetentionCount(value: unknown): string {
  return typeof value === 'number' && Number.isFinite(value) ? String(value) : '-'
}

function formatDetailValue(value: unknown): string {
  if (value === null) return 'null'
  if (typeof value === 'string') return value.trim() || '""'
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function formatDetails(details: SecurityAuditEvent['details']): string {
  if (typeof details === 'string') return details.trim() || '-'
  if (!details || typeof details !== 'object') return '-'
  const entries = Object.entries(details)
  if (entries.length === 0) return '-'
  return entries
    .slice(0, 8)
    .map(([key, value]) => `${key}=${formatDetailValue(value)}`)
    .join(' | ')
}

function resultBadgeClass(result: string): string {
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

function compactAuditEventFilters(filters: SecurityAuditEventFilters): SecurityAuditEventFilters {
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

function hasAuditEventFilters(filters: SecurityAuditEventFilters): boolean {
  const compact = compactAuditEventFilters(filters)
  return Boolean(compact.action || compact.result || compact.category || compact.user_id || compact.since || compact.until)
}

function barClass(kind: CountKind, name: string): string {
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

function valueClass(kind: CountKind, name: string): string {
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

function KpiItem({ label, value, tone = 'default' }: KpiItemProps) {
  const valueTone = {
    default: 'text-text-primary',
    green: 'text-accent-green',
    red: 'text-accent-red',
  }[tone]

  return (
    <div className="min-w-0 rounded-md border border-bg-border bg-bg-primary/30 px-3 py-2">
      <p className="truncate text-[11px] text-text-secondary">{label}</p>
      <p className={`mt-1 truncate text-base font-semibold ${valueTone}`}>{value}</p>
    </div>
  )
}

function CountList({
  title,
  counts,
  kind,
  emptyText,
  mono = false,
  testId,
  selectedName = '',
  onSelectName,
}: CountListProps) {
  const entries = useMemo(() => sortedCountEntries(counts), [counts])
  const maxCount = entries[0]?.[1] ?? 0

  return (
    <div className="overflow-hidden rounded-lg border border-bg-border" data-testid={testId}>
      <div className="flex items-center gap-2 bg-bg-tertiary/60 px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-text-secondary">
        {kind === 'category' ? <Layers3 size={12} /> : <BarChart3 size={12} />}
        <span>{title}</span>
      </div>

      {entries.length === 0 ? (
        <div className="px-3 py-6 text-center text-xs text-text-secondary">{emptyText}</div>
      ) : (
        <div className="max-h-56 overflow-auto">
          {entries.map(([name, count]) => {
            const width = maxCount > 0 ? Math.max(4, Math.round((count / maxCount) * 100)) : 0
            const label = formatCountName(name)
            return (
              <button
                key={name}
                type="button"
                className={`block w-full border-t border-bg-border px-3 py-2 text-left first:border-t-0 ${
                  onSelectName ? 'hover:bg-bg-hover/50' : ''
                } ${selectedName === name ? 'bg-accent-blue/10' : ''}`}
                onClick={() => onSelectName?.(name)}
                data-testid={`${testId}-row`}
              >
                <div className="flex min-w-0 items-center justify-between gap-3 text-xs">
                  <span
                    className={`min-w-0 truncate text-text-primary ${mono ? 'font-mono text-[11px]' : ''}`}
                    title={label}
                  >
                    {label}
                  </span>
                  <span className={`shrink-0 font-semibold ${valueClass(kind, name)}`}>{count}</span>
                </div>
                <div className="mt-2 h-1.5 rounded-full bg-bg-hover">
                  <div
                    className={`h-1.5 rounded-full ${barClass(kind, name)}`}
                    style={{ width: `${width}%` }}
                  />
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

export const SecurityAuditSummaryPanel: React.FC = () => {
  const [category, setCategory] = useState<SecurityAuditSummaryCategory>('all')
  const [limit, setLimit] = useState<number>(200)
  const [summary, setSummary] = useState<SecurityAuditSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [actionFilter, setActionFilter] = useState('')
  const [resultFilter, setResultFilter] = useState('')
  const [eventCategoryFilter, setEventCategoryFilter] = useState('')
  const [userFilter, setUserFilter] = useState('')
  const [sinceFilter, setSinceFilter] = useState('')
  const [untilFilter, setUntilFilter] = useState('')
  const [appliedEventFilters, setAppliedEventFilters] = useState<SecurityAuditEventFilters>({})
  const [events, setEvents] = useState<SecurityAuditEvent[]>([])
  const [eventsTotal, setEventsTotal] = useState(0)
  const [eventsLimit, setEventsLimit] = useState(limit)
  const [eventsLoading, setEventsLoading] = useState(false)
  const [eventsError, setEventsError] = useState<string | null>(null)
  const [retentionKeepLatest, setRetentionKeepLatest] = useState('200')
  const [retentionLoading, setRetentionLoading] = useState<'preview' | 'cleanup' | null>(null)
  const [retentionResult, setRetentionResult] = useState<SecurityAuditCleanupResponse | null>(null)
  const [retentionError, setRetentionError] = useState<string | null>(null)

  const loadSummary = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = await getSecurityAuditSummary(category, limit)
      setSummary(payload)
    } catch (err) {
      setError(normalizeError(err))
    } finally {
      setLoading(false)
    }
  }, [category, limit])

  useEffect(() => {
    void loadSummary()
  }, [loadSummary])

  const loadEvents = useCallback(async (nextLimit = limit, nextFilters = appliedEventFilters) => {
    const compactFilters = compactAuditEventFilters(nextFilters)
    setEventsLoading(true)
    setEventsError(null)
    try {
      const payload = await getSecurityAuditEvents(nextLimit, compactFilters)
      setEvents(payload.events)
      setEventsTotal(payload.total)
      setEventsLimit(payload.limit)
    } catch (err) {
      setEventsError(normalizeError(err, 'Failed to load security audit events'))
    } finally {
      setEventsLoading(false)
    }
  }, [appliedEventFilters, limit])

  useEffect(() => {
    void loadEvents(limit, appliedEventFilters)
  }, [appliedEventFilters, limit, loadEvents])

  const activeCategoryLabel = useMemo(
    () => CATEGORY_OPTIONS.find((option) => option.value === category)?.label ?? 'All',
    [category],
  )

  const activeCategoryCount = useMemo(
    () => sortedCountEntries(summary?.category_counts ?? {}).length,
    [summary],
  )

  const resultOptions = useMemo(() => {
    const names = sortedCountEntries(summary?.result_counts ?? {}).map(([name]) => name)
    return Array.from(new Set(names))
  }, [summary])

  const draftEventFilters = useMemo(
    () => compactAuditEventFilters({
      action: actionFilter,
      result: resultFilter,
      category: eventCategoryFilter,
      user_id: userFilter,
      since: parseDatetimeLocalSeconds(sinceFilter),
      until: parseDatetimeLocalSeconds(untilFilter),
    }),
    [actionFilter, eventCategoryFilter, resultFilter, sinceFilter, untilFilter, userFilter],
  )
  const eventFiltersActive = hasAuditEventFilters(appliedEventFilters)
  const keepLatestNumber = Math.max(0, Math.floor(Number(retentionKeepLatest) || 0))

  const applyEventFilters = () => {
    setAppliedEventFilters(draftEventFilters)
  }

  const resetEventFilters = () => {
    setActionFilter('')
    setResultFilter('')
    setEventCategoryFilter('')
    setUserFilter('')
    setSinceFilter('')
    setUntilFilter('')
    setAppliedEventFilters({})
  }

  const selectActionFilter = (action: string) => {
    setActionFilter(action)
    setAppliedEventFilters(compactAuditEventFilters({
      ...draftEventFilters,
      action,
      result: resultFilter,
    }))
  }

  const previewRetentionCleanup = () => {
    setRetentionError(null)
    setRetentionResult({
      keep_latest: keepLatestNumber,
      would_delete_count: Math.max(0, eventsTotal - keepLatestNumber),
      remaining_count: Math.min(eventsTotal, keepLatestNumber),
      dry_run: true,
    })
  }

  const runRetentionCleanup = async () => {
    setRetentionLoading('cleanup')
    setRetentionError(null)
    try {
      const payload = await cleanupSecurityAuditEvents({ keep_latest: keepLatestNumber })
      setRetentionResult(payload)
      await loadSummary()
      await loadEvents(limit, appliedEventFilters)
    } catch (err) {
      setRetentionError(normalizeError(err, 'Failed to cleanup security audit events'))
    } finally {
      setRetentionLoading(null)
    }
  }

  return (
    <div className="space-y-4" data-testid="settings-security-audit-summary-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-sm font-medium text-text-primary">
          <ShieldCheck size={14} className="text-accent-blue" />
          Security audit
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="input-base py-1 text-xs"
            value={category}
            onChange={(event) => setCategory(event.target.value as SecurityAuditSummaryCategory)}
            data-testid="settings-security-audit-category"
          >
            {CATEGORY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className="input-base py-1 text-xs"
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
            data-testid="settings-security-audit-limit"
          >
            {LIMIT_OPTIONS.map((option) => (
              <option key={option} value={option}>
                Last {option}
              </option>
            ))}
          </select>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void loadSummary()}
            loading={loading}
            data-testid="settings-security-audit-refresh"
          >
            <RefreshCw size={12} />
            Refresh
          </Button>
        </div>
      </div>

      <div className="grid gap-2 rounded-lg border border-bg-border bg-bg-tertiary/30 p-3 text-xs text-text-secondary sm:grid-cols-2 lg:grid-cols-5">
        <KpiItem label="Category" value={activeCategoryLabel} />
        <KpiItem label="Total" value={summary?.total ?? '-'} />
        <KpiItem label="Recent / window" value={summary ? `${summary.recent_count} / ${summary.window_limit}` : '-'} />
        <KpiItem label="Active categories" value={activeCategoryCount} />
        <KpiItem
          label="Unknown actions"
          value={summary?.unknown_action_count ?? '-'}
          tone={summary && summary.unknown_action_count > 0 ? 'red' : 'default'}
        />
      </div>

      {error && (
        <div
          className="flex items-start gap-2 rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red"
          data-testid="settings-security-audit-error"
        >
          <AlertTriangle size={13} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading && !summary && (
        <div className="flex justify-center rounded-lg border border-bg-border py-8">
          <span className="h-5 w-5 animate-spin rounded-full border-2 border-accent-blue border-t-transparent" />
        </div>
      )}

      {summary && (
        <div className="grid gap-3 lg:grid-cols-3">
          <CountList
            title="Actions"
            counts={summary.action_counts}
            kind="action"
            emptyText="No actions in this window."
            mono
            testId="settings-security-audit-actions"
            selectedName={appliedEventFilters.action}
            onSelectName={selectActionFilter}
          />
          <CountList
            title="Results"
            counts={summary.result_counts}
            kind="result"
            emptyText="No results in this window."
            testId="settings-security-audit-results"
          />
          <CountList
            title="Categories"
            counts={summary.category_counts}
            kind="category"
            emptyText="No categories in this window."
            testId="settings-security-audit-categories"
          />
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-bg-border" data-testid="settings-security-audit-events">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-bg-border bg-bg-tertiary/60 px-3 py-2">
          <div className="text-[11px] font-medium uppercase tracking-wide text-text-secondary">
            Events <span className="normal-case tracking-normal">({events.length} / {eventsTotal}, limit {eventsLimit})</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <input
              className="input-base w-56 max-w-full py-1 font-mono text-xs"
              placeholder="action"
              value={actionFilter}
              onChange={(event) => setActionFilter(event.target.value)}
              onKeyDown={(event) => event.key === 'Enter' && applyEventFilters()}
              data-testid="settings-security-audit-event-action-filter"
            />
            <select
              className="input-base py-1 text-xs"
              value={resultFilter}
              onChange={(event) => setResultFilter(event.target.value)}
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
              value={eventCategoryFilter}
              onChange={(event) => setEventCategoryFilter(event.target.value)}
              data-testid="settings-security-audit-event-category-filter"
            >
              <option value="">All categories</option>
              {EVENT_CATEGORY_FILTER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <input
              className="input-base w-40 max-w-full py-1 font-mono text-xs"
              placeholder="user id"
              value={userFilter}
              onChange={(event) => setUserFilter(event.target.value)}
              onKeyDown={(event) => event.key === 'Enter' && applyEventFilters()}
              data-testid="settings-security-audit-event-user-filter"
            />
            <input
              className="input-base w-44 max-w-full py-1 text-xs"
              type="datetime-local"
              value={sinceFilter}
              onChange={(event) => setSinceFilter(event.target.value)}
              data-testid="settings-security-audit-event-since-filter"
            />
            <input
              className="input-base w-44 max-w-full py-1 text-xs"
              type="datetime-local"
              value={untilFilter}
              onChange={(event) => setUntilFilter(event.target.value)}
              data-testid="settings-security-audit-event-until-filter"
            />
            <Button
              variant="primary"
              size="sm"
              onClick={applyEventFilters}
              loading={eventsLoading}
              data-testid="settings-security-audit-event-apply-filters"
            >
              <Search size={12} />
              Filter
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={resetEventFilters}
              disabled={!eventFiltersActive && !hasAuditEventFilters(draftEventFilters)}
              data-testid="settings-security-audit-event-reset-filters"
            >
              <X size={12} />
              Reset
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void loadEvents()}
              loading={eventsLoading}
              data-testid="settings-security-audit-event-refresh"
            >
              <RefreshCw size={12} />
              Refresh
            </Button>
          </div>
        </div>

        {eventsError && (
          <div className="flex items-start gap-2 border-b border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red">
            <AlertTriangle size={13} className="mt-0.5 shrink-0" />
            <span>{eventsError}</span>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-bg-border bg-bg-primary/30 px-3 py-2">
          <div className="flex flex-wrap items-center gap-2 text-xs text-text-secondary">
            <span className="font-medium text-text-primary">Retention</span>
            <input
              className="input-base w-28 py-1 text-xs"
              type="number"
              min={0}
              step={1}
              value={retentionKeepLatest}
              onChange={(event) => setRetentionKeepLatest(event.target.value)}
              data-testid="settings-security-audit-retention-keep-latest"
            />
            <span>keep latest events</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={previewRetentionCleanup}
              loading={retentionLoading === 'preview'}
              data-testid="settings-security-audit-retention-preview"
            >
              <Search size={12} />
              Preview
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void runRetentionCleanup()}
              loading={retentionLoading === 'cleanup'}
              data-testid="settings-security-audit-retention-cleanup"
            >
              <Trash2 size={12} />
              Cleanup
            </Button>
          </div>
          {(retentionResult || retentionError) && (
            <div
              className={`basis-full rounded-md border px-3 py-2 text-xs ${
                retentionError
                  ? 'border-accent-red/30 bg-accent-red/10 text-accent-red'
                  : 'border-bg-border bg-bg-tertiary/40 text-text-secondary'
              }`}
              data-testid="settings-security-audit-retention-result"
            >
              {retentionError ? (
                <span>{retentionError}</span>
              ) : retentionResult ? (
                <span>
                  {retentionResult.dry_run ? 'Would delete' : 'Deleted'}{' '}
                  {formatRetentionCount(retentionResult.would_delete_count ?? retentionResult.deleted_count)}
                  {' '}events, remaining {formatRetentionCount(retentionResult.remaining_count)}
                  {' '}with keep latest {formatRetentionCount(retentionResult.keep_latest)}.
                </span>
              ) : null}
            </div>
          )}
        </div>

        <div className="hidden grid-cols-[minmax(11rem,1.2fr)_minmax(12rem,1.2fr)_6rem_minmax(11rem,1fr)_minmax(14rem,1.4fr)] gap-3 bg-bg-tertiary/40 px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-text-secondary md:grid">
          <span>Time</span>
          <span>Action</span>
          <span>Result</span>
          <span>Actor</span>
          <span>Details</span>
        </div>

        {eventsLoading && events.length === 0 && (
          <div className="flex justify-center py-8">
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-accent-blue border-t-transparent" />
          </div>
        )}

        {!eventsLoading && events.length === 0 && (
          <div className="px-3 py-8 text-center text-xs text-text-secondary">
            No audit events.
          </div>
        )}

        {events.map((event, index) => {
          const details = clampText(formatDetails(event.details))
          const actor = [event.user_role, event.user_id].filter(Boolean).join(': ') || '-'
          const requestMeta = [event.request_id, event.ip].filter(Boolean).join(' | ')
          return (
            <div
              key={`${event.request_id}:${event.action}:${event.timestamp}:${index}`}
              className="grid gap-2 border-t border-bg-border px-3 py-2 text-xs text-text-secondary first:border-t-0 md:grid-cols-[minmax(11rem,1.2fr)_minmax(12rem,1.2fr)_6rem_minmax(11rem,1fr)_minmax(14rem,1.4fr)] md:gap-3"
              data-testid="settings-security-audit-event-row"
            >
              <div className="min-w-0">
                <p className="truncate text-text-primary">{formatTimestamp(event.timestamp)}</p>
                <p className="mt-0.5 truncate font-mono text-[10px] text-text-secondary/70" title={requestMeta}>
                  {requestMeta || '-'}
                </p>
              </div>
              <div className="min-w-0">
                <p className="truncate font-mono text-[11px] text-text-primary" title={event.action || '-'}>
                  {event.action || '-'}
                </p>
                <p className="mt-0.5 truncate text-[10px] text-text-secondary/70">
                  {event.auth_mode || '-'} / {event.auth_source || '-'}{event.is_local ? ' / local' : ''}
                </p>
              </div>
              <div>
                <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${resultBadgeClass(event.result)}`}>
                  {event.result || '-'}
                </span>
              </div>
              <div className="min-w-0 truncate" title={actor}>
                {actor}
              </div>
              <div className="min-w-0 truncate font-mono text-[11px]" title={formatDetails(event.details)}>
                {details}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
