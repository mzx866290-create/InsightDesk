import type {
  TraceDashboardCard,
  TraceEvent,
  TraceEventKind,
  TraceFilters,
  TracePanelTemplate,
  TraceSummary,
} from '../../api/client'

export const TRACE_LIMIT_OPTIONS = [50, 100, 200, 500] as const

export const TRACE_EVENT_STYLE: Record<TraceEventKind, string> = {
  start: 'bg-accent-blue/15 text-accent-blue',
  end: 'bg-accent-green/15 text-accent-green',
  error: 'bg-accent-red/15 text-accent-red',
}

export function shortId(id: string | null): string {
  return id ? id.slice(0, 8) : '-'
}

export function clampText(value: string, limit = 72): string {
  return value.length > limit ? `${value.slice(0, limit - 1)}...` : value
}

export function formatDuration(durationMs: number | null): string {
  if (typeof durationMs !== 'number' || !Number.isFinite(durationMs)) return '-'
  if (durationMs >= 1000) return `${(durationMs / 1000).toFixed(2)} s`
  return `${durationMs.toFixed(durationMs >= 10 ? 1 : 2)} ms`
}

export function formatTimestamp(timestamp: number): string {
  if (!Number.isFinite(timestamp)) return '-'
  return new Date(timestamp * 1000).toLocaleString('zh-CN', { hour12: false })
}

export function formatAttributeValue(value: unknown): string {
  if (value === null) return 'null'
  if (typeof value === 'string') return value.trim() || '""'
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

export function attributesSummary(attributes: Record<string, unknown>): string {
  const entries = Object.entries(attributes)
  if (entries.length === 0) return '-'

  const visible = entries.slice(0, 5).map(([key, value]) => (
    `${key}=${clampText(formatAttributeValue(value), 48)}`
  ))
  const hiddenCount = entries.length - visible.length
  return hiddenCount > 0 ? `${visible.join(' | ')} | +${hiddenCount}` : visible.join(' | ')
}

export function compactTraceFilters(filters: TraceFilters): TraceFilters {
  return {
    event: filters.event || '',
    name: filters.name?.trim() || '',
    trace_id: filters.trace_id?.trim() || '',
    span_id: filters.span_id?.trim() || '',
  }
}

export function hasTraceFilters(filters: TraceFilters): boolean {
  const compact = compactTraceFilters(filters)
  return Boolean(compact.event || compact.name || compact.trace_id || compact.span_id)
}

export function normalizeSummary(limit: number, filters: TraceFilters = {}): TraceSummary {
  return { returned: 0, limit, error_events: 0, filters: compactTraceFilters(filters) }
}

export function normalizeDashboardCards(cards: TraceDashboardCard[] | undefined): TraceDashboardCard[] {
  return Array.isArray(cards) ? cards.slice(0, 4) : []
}

export function normalizePanelTemplates(templates: TracePanelTemplate[] | undefined): TracePanelTemplate[] {
  return Array.isArray(templates) ? templates.slice(0, 2) : []
}

export function latestTraceTimestamp(events: TraceEvent[]): string {
  const latest = events.reduce((max, event) => Math.max(max, event.timestamp), 0)
  return latest > 0 ? formatTimestamp(latest) : '-'
}

export function traceActionErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : String(error || fallback)
}

export function formatNodeSummary(nodes: Record<string, number> | undefined): string {
  const entries = Object.entries(nodes ?? {}).slice(0, 3)
  if (entries.length === 0) return '-'
  return entries.map(([name, count]) => `${name}:${count}`).join(' | ')
}

export interface TraceWaterfallSpanRow {
  traceId: string
  spanId: string
  parentSpanId: string | null
  name: string
  event: TraceEventKind
  timestamp: number
  durationMs: number | null
  depth: number
  offsetPercent: number
  widthPercent: number
  errorText: string
  attributes: Record<string, unknown>
}

export interface TraceWaterfallGroup {
  traceId: string
  startTimestamp: number
  endTimestamp: number
  durationMs: number
  rows: TraceWaterfallSpanRow[]
}

interface TraceSpanAggregate {
  traceId: string
  spanId: string
  parentSpanId: string | null
  name: string
  event: TraceEventKind
  timestamp: number
  lastTimestamp: number
  durationMs: number | null
  attributes: Record<string, unknown>
  errorText: string
}

const TRACE_EVENT_PRIORITY: Record<TraceEventKind, number> = {
  start: 0,
  end: 1,
  error: 2,
}

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(100, value))
}

function toWaterfallRow(
  span: TraceSpanAggregate,
  depth: number,
  timelineStart: number,
  timelineDurationSeconds: number,
): TraceWaterfallSpanRow {
  const durationMs = span.durationMs ?? Math.max(0, (span.lastTimestamp - span.timestamp) * 1000)
  const durationSeconds = Math.max(0, durationMs / 1000)
  const offsetPercent = timelineDurationSeconds > 0
    ? ((span.timestamp - timelineStart) / timelineDurationSeconds) * 100
    : 0
  const rawWidthPercent = timelineDurationSeconds > 0
    ? (durationSeconds / timelineDurationSeconds) * 100
    : 100

  return {
    traceId: span.traceId,
    spanId: span.spanId,
    parentSpanId: span.parentSpanId,
    name: span.name,
    event: span.event,
    timestamp: span.timestamp,
    durationMs,
    depth,
    offsetPercent: clampPercent(offsetPercent),
    widthPercent: clampPercent(Math.max(rawWidthPercent, 1.5)),
    errorText: span.errorText,
    attributes: span.attributes,
  }
}

function sortTraceSpans(spans: TraceSpanAggregate[]): TraceSpanAggregate[] {
  return [...spans].sort((a, b) => (
    a.timestamp - b.timestamp
    || a.lastTimestamp - b.lastTimestamp
    || a.name.localeCompare(b.name)
    || a.spanId.localeCompare(b.spanId)
  ))
}

function buildTraceRows(spans: TraceSpanAggregate[], timelineStart: number, timelineDurationSeconds: number): TraceWaterfallSpanRow[] {
  const spansById = new Map(spans.map((span) => [span.spanId, span]))
  const childrenByParent = new Map<string, TraceSpanAggregate[]>()
  const hasLinkedParent = spans.some((span) => span.parentSpanId && spansById.has(span.parentSpanId))

  if (!hasLinkedParent) {
    return sortTraceSpans(spans).map((span) => toWaterfallRow(span, 0, timelineStart, timelineDurationSeconds))
  }

  for (const span of spans) {
    if (!span.parentSpanId || !spansById.has(span.parentSpanId)) continue
    const children = childrenByParent.get(span.parentSpanId) ?? []
    children.push(span)
    childrenByParent.set(span.parentSpanId, children)
  }

  for (const [parentSpanId, children] of childrenByParent) {
    childrenByParent.set(parentSpanId, sortTraceSpans(children))
  }

  const rows: TraceWaterfallSpanRow[] = []
  const visited = new Set<string>()

  const visit = (span: TraceSpanAggregate, depth: number) => {
    if (visited.has(span.spanId)) return
    visited.add(span.spanId)
    rows.push(toWaterfallRow(span, depth, timelineStart, timelineDurationSeconds))
    for (const child of childrenByParent.get(span.spanId) ?? []) {
      visit(child, depth + 1)
    }
  }

  const roots = sortTraceSpans(spans.filter((span) => !span.parentSpanId || !spansById.has(span.parentSpanId)))
  for (const root of roots) visit(root, 0)
  for (const span of sortTraceSpans(spans)) visit(span, 0)

  return rows
}

export function buildTraceWaterfallGroups(events: TraceEvent[]): TraceWaterfallGroup[] {
  const spansByTrace = new Map<string, Map<string, TraceSpanAggregate>>()

  for (const event of events) {
    const traceSpans = spansByTrace.get(event.trace_id) ?? new Map<string, TraceSpanAggregate>()
    const existing = traceSpans.get(event.span_id)
    const errorText = [event.error_type, event.error_message].filter(Boolean).join(': ')

    if (!existing) {
      traceSpans.set(event.span_id, {
        traceId: event.trace_id,
        spanId: event.span_id,
        parentSpanId: event.parent_span_id ?? null,
        name: event.name || 'span',
        event: event.event,
        timestamp: event.timestamp,
        lastTimestamp: event.timestamp,
        durationMs: event.duration_ms,
        attributes: event.attributes,
        errorText,
      })
    } else {
      const isLatestEvent = event.timestamp >= existing.lastTimestamp
      existing.parentSpanId = existing.parentSpanId ?? event.parent_span_id ?? null
      existing.name = event.name || existing.name
      existing.timestamp = Math.min(existing.timestamp, event.timestamp)
      existing.lastTimestamp = Math.max(existing.lastTimestamp, event.timestamp)
      existing.durationMs = typeof event.duration_ms === 'number' && Number.isFinite(event.duration_ms)
        ? event.duration_ms
        : existing.durationMs
      existing.attributes = isLatestEvent ? event.attributes : existing.attributes
      existing.errorText = errorText || existing.errorText
      existing.event = TRACE_EVENT_PRIORITY[event.event] >= TRACE_EVENT_PRIORITY[existing.event]
        ? event.event
        : existing.event
    }

    spansByTrace.set(event.trace_id, traceSpans)
  }

  return [...spansByTrace.entries()]
    .map(([traceId, traceSpans]) => {
      const spans = [...traceSpans.values()]
      const startTimestamp = Math.min(...spans.map((span) => span.timestamp))
      const endTimestamp = Math.max(...spans.map((span) => (
        span.timestamp + ((span.durationMs ?? Math.max(0, (span.lastTimestamp - span.timestamp) * 1000)) / 1000)
      )))
      const timelineDurationSeconds = Math.max(0, endTimestamp - startTimestamp)

      return {
        traceId,
        startTimestamp,
        endTimestamp,
        durationMs: timelineDurationSeconds * 1000,
        rows: buildTraceRows(spans, startTimestamp, timelineDurationSeconds),
      }
    })
    .sort((a, b) => b.startTimestamp - a.startTimestamp || a.traceId.localeCompare(b.traceId))
}
