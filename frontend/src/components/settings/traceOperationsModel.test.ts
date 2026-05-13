import { afterEach, describe, expect, it, vi } from 'vitest'

import type { TraceDashboardCard, TracePanelTemplate } from '../../api/client'
import {
  TRACE_EVENT_STYLE,
  attributesSummary,
  buildTraceWaterfallGroups,
  clampText,
  compactTraceFilters,
  formatAttributeValue,
  formatDuration,
  formatNodeSummary,
  formatTimestamp,
  hasTraceFilters,
  latestTraceTimestamp,
  normalizeDashboardCards,
  normalizePanelTemplates,
  normalizeSummary,
  shortId,
  traceActionErrorMessage,
} from './traceOperationsModel'

describe('traceOperationsModel', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shortens ids and clamps text', () => {
    expect(shortId(null)).toBe('-')
    expect(shortId('1234567890abcdef')).toBe('12345678')
    expect(clampText('short', 10)).toBe('short')
    expect(clampText('x'.repeat(12), 10)).toBe(`${'x'.repeat(9)}...`)
  })

  it('formats durations across missing, millisecond and second values', () => {
    expect(formatDuration(null)).toBe('-')
    expect(formatDuration(Number.NaN)).toBe('-')
    expect(formatDuration(4.321)).toBe('4.32 ms')
    expect(formatDuration(12.34)).toBe('12.3 ms')
    expect(formatDuration(1234)).toBe('1.23 s')
  })

  it('formats timestamps and falls back on invalid values', () => {
    vi.spyOn(Date.prototype, 'toLocaleString').mockReturnValue('2026/05/08 14:45:00')

    expect(formatTimestamp(Number.NaN)).toBe('-')
    expect(formatTimestamp(1_715_000_000)).toBe('2026/05/08 14:45:00')
    expect(Date.prototype.toLocaleString).toHaveBeenCalledWith('zh-CN', { hour12: false })
  })

  it('formats attribute values and summaries', () => {
    expect(formatAttributeValue(null)).toBe('null')
    expect(formatAttributeValue('  ')).toBe('""')
    expect(formatAttributeValue(12)).toBe('12')
    expect(formatAttributeValue(true)).toBe('true')
    expect(formatAttributeValue({ nested: 'value' })).toBe('{"nested":"value"}')

    expect(attributesSummary({})).toBe('-')
    expect(attributesSummary({
      a: 'one',
      b: 2,
      c: false,
      d: null,
      e: { nested: 'value' },
      f: 'hidden',
    })).toBe('a=one | b=2 | c=false | d=null | e={"nested":"value"} | +1')
  })

  it('compacts and detects trace filters', () => {
    expect(compactTraceFilters({
      event: 'error',
      name: ' span ',
      trace_id: ' trace ',
      span_id: ' span-id ',
    })).toEqual({
      event: 'error',
      name: 'span',
      trace_id: 'trace',
      span_id: 'span-id',
    })

    expect(hasTraceFilters({ name: '  ' })).toBe(false)
    expect(hasTraceFilters({ span_id: 'abc' })).toBe(true)
  })

  it('normalizes summary, cards and panel templates', () => {
    expect(normalizeSummary(100, { name: ' span ' })).toEqual({
      returned: 0,
      limit: 100,
      error_events: 0,
      filters: {
        event: '',
        name: 'span',
        trace_id: '',
        span_id: '',
      },
    })

    const cards = Array.from({ length: 6 }, (_, index): TraceDashboardCard => ({
      id: `card-${index}`,
      title: `Card ${index}`,
      value: index,
    }))
    const templates = Array.from({ length: 4 }, (_, index): TracePanelTemplate => ({
      id: `template-${index}`,
      title: `Template ${index}`,
      kind: 'stat',
      source: 'trace',
      fields: [],
    }))

    expect(normalizeDashboardCards(cards).map((card) => card.id)).toEqual(['card-0', 'card-1', 'card-2', 'card-3'])
    expect(normalizeDashboardCards(undefined)).toEqual([])
    expect(normalizePanelTemplates(templates).map((template) => template.id)).toEqual(['template-0', 'template-1'])
    expect(normalizePanelTemplates(undefined)).toEqual([])
  })

  it('formats node summaries and exposes event style mapping', () => {
    expect(formatNodeSummary(undefined)).toBe('-')
    expect(formatNodeSummary({ api: 2, worker: 3, db: 1, ignored: 9 })).toBe('api:2 | worker:3 | db:1')
    expect(TRACE_EVENT_STYLE.error).toContain('text-accent-red')
  })

  it('derives latest timestamps and normalizes action errors', () => {
    vi.spyOn(Date.prototype, 'toLocaleString').mockReturnValue('2026/05/08 14:45:00')

    expect(latestTraceTimestamp([])).toBe('-')
    expect(latestTraceTimestamp([
      {
        event: 'start',
        name: 'older',
        trace_id: 'trace-1',
        span_id: 'span-1',
        parent_span_id: null,
        timestamp: 1,
        duration_ms: null,
        attributes: {},
        error_type: null,
        error_message: null,
      },
      {
        event: 'end',
        name: 'newer',
        trace_id: 'trace-2',
        span_id: 'span-2',
        parent_span_id: null,
        timestamp: 1_715_000_000,
        duration_ms: 12,
        attributes: {},
        error_type: null,
        error_message: null,
      },
    ])).toBe('2026/05/08 14:45:00')
    expect(traceActionErrorMessage(new Error('boom'), 'fallback')).toBe('boom')
    expect(traceActionErrorMessage(null, 'fallback')).toBe('fallback')
  })

  it('builds nested waterfall groups when parent span ids are present', () => {
    const groups = buildTraceWaterfallGroups([
      {
        event: 'start',
        name: 'tool.execute',
        trace_id: 'trace-1',
        span_id: 'child-1',
        parent_span_id: 'root-1',
        timestamp: 102,
        duration_ms: null,
        attributes: { tool: 'search' },
        error_type: null,
        error_message: null,
      },
      {
        event: 'end',
        name: 'llm.invoke',
        trace_id: 'trace-1',
        span_id: 'root-1',
        parent_span_id: null,
        timestamp: 100,
        duration_ms: 5_000,
        attributes: { model: 'gpt' },
        error_type: null,
        error_message: null,
      },
      {
        event: 'error',
        name: 'tool.execute',
        trace_id: 'trace-1',
        span_id: 'child-1',
        parent_span_id: 'root-1',
        timestamp: 103,
        duration_ms: 1_000,
        attributes: { tool: 'search', failed: true },
        error_type: 'ToolError',
        error_message: 'boom',
      },
    ])

    expect(groups).toHaveLength(1)
    expect(groups[0].traceId).toBe('trace-1')
    expect(groups[0].durationMs).toBe(5_000)
    expect(groups[0].rows.map((row) => [row.spanId, row.depth, row.event])).toEqual([
      ['root-1', 0, 'end'],
      ['child-1', 1, 'error'],
    ])
    expect(groups[0].rows[1].errorText).toBe('ToolError: boom')
    expect(groups[0].rows[1].attributes).toEqual({ tool: 'search', failed: true })
  })

  it('falls back to a flat timeline when parent span ids are unavailable', () => {
    const groups = buildTraceWaterfallGroups([
      {
        event: 'end',
        name: 'later',
        trace_id: 'trace-flat',
        span_id: 'span-2',
        timestamp: 20,
        duration_ms: 10,
        attributes: {},
        error_type: null,
        error_message: null,
      },
      {
        event: 'start',
        name: 'earlier',
        trace_id: 'trace-flat',
        span_id: 'span-1',
        timestamp: 10,
        duration_ms: null,
        attributes: {},
        error_type: null,
        error_message: null,
      },
    ])

    expect(groups[0].rows.map((row) => [row.spanId, row.depth])).toEqual([
      ['span-1', 0],
      ['span-2', 0],
    ])
  })
})
