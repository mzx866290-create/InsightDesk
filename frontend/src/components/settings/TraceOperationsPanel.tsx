import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, BarChart3, FileJson, RefreshCw, Search, Trash2, X } from 'lucide-react'

import {
  clearTraceEvents,
  getTraceEvents,
} from '../../api/client'
import type {
  TraceEvent,
  TraceDashboardCard,
  TraceEventKind,
  TraceExportPreview,
  TraceFilters,
  TracePanelTemplate,
  TraceSummary,
} from '../../api/client'
import { Button } from '../ui/Button'

const TRACE_LIMIT_OPTIONS = [50, 100, 200, 500] as const

const EVENT_STYLE: Record<TraceEventKind, string> = {
  start: 'bg-accent-blue/15 text-accent-blue',
  end: 'bg-accent-green/15 text-accent-green',
  error: 'bg-accent-red/15 text-accent-red',
}

function shortId(id: string | null): string {
  return id ? id.slice(0, 8) : '-'
}

function clampText(value: string, limit = 72): string {
  return value.length > limit ? `${value.slice(0, limit - 1)}...` : value
}

function formatDuration(durationMs: number | null): string {
  if (typeof durationMs !== 'number' || !Number.isFinite(durationMs)) return '-'
  if (durationMs >= 1000) return `${(durationMs / 1000).toFixed(2)} s`
  return `${durationMs.toFixed(durationMs >= 10 ? 1 : 2)} ms`
}

function formatTimestamp(timestamp: number): string {
  if (!Number.isFinite(timestamp)) return '-'
  return new Date(timestamp * 1000).toLocaleString('zh-CN', { hour12: false })
}

function formatAttributeValue(value: unknown): string {
  if (value === null) return 'null'
  if (typeof value === 'string') return value.trim() || '""'
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function attributesSummary(attributes: Record<string, unknown>): string {
  const entries = Object.entries(attributes)
  if (entries.length === 0) return '-'

  const visible = entries.slice(0, 5).map(([key, value]) => (
    `${key}=${clampText(formatAttributeValue(value), 48)}`
  ))
  const hiddenCount = entries.length - visible.length
  return hiddenCount > 0 ? `${visible.join(' | ')} | +${hiddenCount}` : visible.join(' | ')
}

function compactTraceFilters(filters: TraceFilters): TraceFilters {
  return {
    event: filters.event || '',
    name: filters.name?.trim() || '',
    trace_id: filters.trace_id?.trim() || '',
    span_id: filters.span_id?.trim() || '',
  }
}

function hasTraceFilters(filters: TraceFilters): boolean {
  const compact = compactTraceFilters(filters)
  return Boolean(compact.event || compact.name || compact.trace_id || compact.span_id)
}

function normalizeSummary(limit: number, filters: TraceFilters = {}): TraceSummary {
  return { returned: 0, limit, error_events: 0, filters: compactTraceFilters(filters) }
}

function normalizeDashboardCards(cards: TraceDashboardCard[] | undefined): TraceDashboardCard[] {
  return Array.isArray(cards) ? cards.slice(0, 4) : []
}

function normalizePanelTemplates(templates: TracePanelTemplate[] | undefined): TracePanelTemplate[] {
  return Array.isArray(templates) ? templates.slice(0, 2) : []
}

function formatNodeSummary(nodes: Record<string, number> | undefined): string {
  const entries = Object.entries(nodes ?? {}).slice(0, 3)
  if (entries.length === 0) return '-'
  return entries.map(([name, count]) => `${name}:${count}`).join(' | ')
}

export const TraceOperationsPanel: React.FC = () => {
  const [limit, setLimit] = useState<number>(100)
  const [eventFilter, setEventFilter] = useState<TraceEventKind | ''>('')
  const [nameFilter, setNameFilter] = useState('')
  const [traceIdFilter, setTraceIdFilter] = useState('')
  const [spanIdFilter, setSpanIdFilter] = useState('')
  const [appliedFilters, setAppliedFilters] = useState<TraceFilters>({})
  const [events, setEvents] = useState<TraceEvent[]>([])
  const [summary, setSummary] = useState<TraceSummary>(() => normalizeSummary(100))
  const [dashboardCards, setDashboardCards] = useState<TraceDashboardCard[]>([])
  const [panelTemplates, setPanelTemplates] = useState<TracePanelTemplate[]>([])
  const [exportPreview, setExportPreview] = useState<TraceExportPreview | null>(null)
  const [loading, setLoading] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const draftFilters = useMemo(
    () =>
      compactTraceFilters({
        event: eventFilter,
        name: nameFilter,
        trace_id: traceIdFilter,
        span_id: spanIdFilter,
      }),
    [eventFilter, nameFilter, spanIdFilter, traceIdFilter],
  )

  const loadTraces = useCallback(async (nextLimit = limit, nextFilters = appliedFilters) => {
    const compactFilters = compactTraceFilters(nextFilters)
    setLoading(true)
    setError(null)
    setNotice(null)
    try {
      const data = await getTraceEvents(nextLimit, compactFilters)
      setEvents(data.events)
      setSummary(data.summary ?? normalizeSummary(nextLimit, compactFilters))
      setDashboardCards(normalizeDashboardCards(data.dashboard_cards))
      setPanelTemplates(normalizePanelTemplates(data.panel_templates))
      setExportPreview(data.export_preview ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || '加载 Trace 失败'))
    } finally {
      setLoading(false)
    }
  }, [appliedFilters, limit])

  useEffect(() => {
    void loadTraces(limit, appliedFilters)
  }, [appliedFilters, limit, loadTraces])

  const handleApplyFilters = () => {
    setAppliedFilters(draftFilters)
  }

  const handleResetFilters = () => {
    setEventFilter('')
    setNameFilter('')
    setTraceIdFilter('')
    setSpanIdFilter('')
    setAppliedFilters({})
  }

  const handleClear = async () => {
    setClearing(true)
    setError(null)
    setNotice(null)
    try {
      await clearTraceEvents()
      setEvents([])
      setSummary(normalizeSummary(limit, appliedFilters))
      setDashboardCards([])
      setPanelTemplates([])
      setExportPreview(null)
      setNotice('Trace cleared')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || '清空 Trace 失败'))
    } finally {
      setClearing(false)
    }
  }

  const latestTimestamp = useMemo(() => {
    const latest = events.reduce((max, event) => Math.max(max, event.timestamp), 0)
    return latest > 0 ? formatTimestamp(latest) : '-'
  }, [events])
  const filtersActive = hasTraceFilters(appliedFilters)

  return (
    <div className="space-y-4" data-testid="settings-trace-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-sm font-medium text-text-primary">
          <AlertTriangle size={14} className="text-accent-blue" />
          Trace 运维
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="input-base py-1 text-xs"
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
            data-testid="settings-trace-limit"
          >
            {TRACE_LIMIT_OPTIONS.map((option) => (
              <option key={option} value={option}>
                最近 {option}
              </option>
            ))}
          </select>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void loadTraces()}
            loading={loading}
            data-testid="settings-trace-refresh"
          >
            <RefreshCw size={12} />
            刷新
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void handleClear()}
            loading={clearing}
            disabled={events.length === 0}
            className="text-accent-red hover:text-accent-red"
            data-testid="settings-trace-clear"
          >
            <Trash2 size={12} />
            清空
          </Button>
        </div>
      </div>

      <div className="grid gap-2 rounded-lg border border-bg-border bg-bg-tertiary/30 p-3 text-xs text-text-secondary md:grid-cols-[8rem_minmax(9rem,1fr)_minmax(10rem,1fr)_minmax(10rem,1fr)_auto]">
        <select
          className="input-base py-1 text-xs"
          value={eventFilter}
          onChange={(event) => setEventFilter(event.target.value as TraceEventKind | '')}
          data-testid="settings-trace-filter-event"
        >
          <option value="">全部事件</option>
          <option value="start">start</option>
          <option value="end">end</option>
          <option value="error">error</option>
        </select>
        <input
          className="input-base py-1 text-xs"
          placeholder="Span name"
          value={nameFilter}
          onChange={(event) => setNameFilter(event.target.value)}
          onKeyDown={(event) => event.key === 'Enter' && handleApplyFilters()}
          data-testid="settings-trace-filter-name"
        />
        <input
          className="input-base py-1 font-mono text-xs"
          placeholder="Trace ID"
          value={traceIdFilter}
          onChange={(event) => setTraceIdFilter(event.target.value)}
          onKeyDown={(event) => event.key === 'Enter' && handleApplyFilters()}
          data-testid="settings-trace-filter-trace-id"
        />
        <input
          className="input-base py-1 font-mono text-xs"
          placeholder="Span ID"
          value={spanIdFilter}
          onChange={(event) => setSpanIdFilter(event.target.value)}
          onKeyDown={(event) => event.key === 'Enter' && handleApplyFilters()}
          data-testid="settings-trace-filter-span-id"
        />
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            size="sm"
            onClick={handleApplyFilters}
            loading={loading}
            data-testid="settings-trace-apply-filters"
          >
            <Search size={12} />
            筛选
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleResetFilters}
            disabled={!filtersActive && !hasTraceFilters(draftFilters)}
            data-testid="settings-trace-reset-filters"
          >
            <X size={12} />
            重置
          </Button>
        </div>
      </div>

      <div className="grid gap-2 rounded-lg border border-bg-border bg-bg-tertiary/30 px-3 py-2 text-xs text-text-secondary sm:grid-cols-4">
        <span>返回：<b className="text-text-primary">{summary.returned}</b> / {summary.limit}</span>
        <span>错误：<b className="text-accent-red">{summary.error_events}</b></span>
        <span>最新：<b className="text-text-primary">{latestTimestamp}</b></span>
        <span>筛选：<b className="text-text-primary" data-testid="settings-trace-filter-status">{filtersActive ? 'filtered' : 'all'}</b></span>
      </div>

      {(dashboardCards.length > 0 || exportPreview) && (
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.8fr)]">
          <div className="rounded-lg border border-bg-border bg-bg-tertiary/30 p-3">
            <div className="mb-2 flex items-center gap-2 text-xs font-medium text-text-primary">
              <BarChart3 size={13} className="text-accent-blue" />
              Dashboard cards
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {dashboardCards.map((card) => (
                <div key={card.id} className="rounded border border-bg-border bg-bg-primary/40 px-3 py-2">
                  <p className="truncate text-[11px] text-text-secondary">{card.title}</p>
                  <p className={card.severity === 'warning' || card.severity === 'error' ? 'mt-1 font-mono text-sm text-accent-red' : 'mt-1 font-mono text-sm text-text-primary'}>
                    {card.value}
                    {card.unit ? <span className="ml-1 text-[10px] text-text-secondary">{card.unit}</span> : null}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-bg-border bg-bg-tertiary/30 p-3">
            <div className="mb-2 flex items-center gap-2 text-xs font-medium text-text-primary">
              <FileJson size={13} className="text-accent-green" />
              OTLP export preview
            </div>
            <div className="space-y-1.5 text-xs text-text-secondary">
              <p>service.name：<b className="text-text-primary">{exportPreview?.service_name ?? '-'}</b></p>
              <p>spans/logs：<b className="text-text-primary">{exportPreview?.span_count ?? 0}</b> / {exportPreview?.log_record_count ?? 0}</p>
              <p>sources：<b className="text-text-primary">{formatNodeSummary(exportPreview?.source_nodes)}</b></p>
              <p>processes：<b className="text-text-primary">{formatNodeSummary(exportPreview?.process_nodes)}</b></p>
              <p>avg duration：<b className="text-text-primary">{formatDuration(exportPreview?.avg_duration_ms ?? null)}</b></p>
              {panelTemplates.length > 0 && (
                <p className="truncate" title={panelTemplates.map((template) => template.title).join(' | ')}>
                  templates：<b className="text-text-primary">{panelTemplates.map((template) => template.id).join(' | ')}</b>
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {(error || notice) && (
        <div
          className={`rounded-lg border px-3 py-2 text-xs ${
            error
              ? 'border-accent-red/30 bg-accent-red/10 text-accent-red'
              : 'border-accent-green/30 bg-accent-green/10 text-accent-green'
          }`}
          data-testid="settings-trace-message"
        >
          {error ?? notice}
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-bg-border" data-testid="settings-trace-event-list">
        <div className="hidden grid-cols-[minmax(10rem,1.25fr)_5rem_6rem_minmax(9rem,1fr)_minmax(12rem,1.4fr)] gap-3 bg-bg-tertiary/60 px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-text-secondary md:grid">
          <span>Name</span>
          <span>Event</span>
          <span>Duration</span>
          <span>Error</span>
          <span>Attributes</span>
        </div>

        {loading && events.length === 0 && (
          <div className="flex justify-center py-8">
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-accent-blue border-t-transparent" />
          </div>
        )}

        {!loading && events.length === 0 && (
          <div className="px-3 py-8 text-center text-xs text-text-secondary" data-testid="settings-trace-empty">
            暂无 Trace。
          </div>
        )}

        {events.map((event) => {
          const errorText = [event.error_type, event.error_message].filter(Boolean).join(': ') || '-'
          return (
            <div
              key={`${event.trace_id}:${event.span_id}:${event.event}:${event.timestamp}`}
              className="grid gap-2 border-t border-bg-border px-3 py-2 text-xs text-text-secondary first:border-t-0 md:grid-cols-[minmax(10rem,1.25fr)_5rem_6rem_minmax(9rem,1fr)_minmax(12rem,1.4fr)] md:gap-3"
              data-testid="settings-trace-event-row"
            >
              <div className="min-w-0">
                <p className="truncate font-medium text-text-primary">{event.name || 'span'}</p>
                <p className="mt-0.5 truncate font-mono text-[10px] text-text-secondary/70">
                  {shortId(event.trace_id)} / {shortId(event.span_id)} | {formatTimestamp(event.timestamp)}
                </p>
              </div>
              <div>
                <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${EVENT_STYLE[event.event]}`}>
                  {event.event}
                </span>
              </div>
              <div className="font-mono text-[11px] text-text-primary">{formatDuration(event.duration_ms)}</div>
              <div className={`min-w-0 truncate ${event.event === 'error' ? 'text-accent-red' : ''}`} title={errorText}>
                {clampText(errorText)}
              </div>
              <div className="min-w-0 truncate text-[11px]" title={attributesSummary(event.attributes)}>
                {attributesSummary(event.attributes)}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
