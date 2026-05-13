import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { TraceEvent, TraceEventsResponse } from '../../api/client'
import { useTraceOperationsPanel } from './useTraceOperationsPanel'

const mocks = vi.hoisted(() => ({
  clearTraceEvents: vi.fn(),
  getTraceEvents: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return {
    ...actual,
    clearTraceEvents: mocks.clearTraceEvents,
    getTraceEvents: mocks.getTraceEvents,
  }
})

const traceEvent = (patch: Partial<TraceEvent> = {}): TraceEvent => ({
  event: 'error',
  name: 'fetch-users',
  trace_id: 'trace-1',
  span_id: 'span-1',
  parent_span_id: null,
  timestamp: 1_715_000_000,
  duration_ms: 42,
  attributes: {},
  error_type: 'TimeoutError',
  error_message: 'request timed out',
  ...patch,
})

const traceResponse = (
  patch: Partial<TraceEventsResponse> = {},
): TraceEventsResponse => ({
  events: [traceEvent()],
  summary: {
    returned: 1,
    limit: 100,
    error_events: 1,
    filters: { event: '', name: '', trace_id: '', span_id: '' },
  },
  dashboard_cards: [
    { id: 'errors', title: 'Errors', value: 1 },
    { id: 'latency', title: 'Latency', value: '42 ms' },
  ],
  panel_templates: [
    { id: 'overview', title: 'Overview', kind: 'table', source: 'trace', fields: ['name'] },
  ],
  export_preview: {
    service_name: 'insightdesk',
    span_count: 1,
    log_record_count: 1,
    source_nodes: {},
    process_nodes: {},
    avg_duration_ms: 42,
    sample_spans: [],
  },
  ...patch,
})

describe('useTraceOperationsPanel', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('loads initial trace data and normalizes preview state', async () => {
    mocks.getTraceEvents.mockResolvedValue(traceResponse())

    const { result } = renderHook(() => useTraceOperationsPanel())

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(mocks.getTraceEvents).toHaveBeenCalledWith(100, {
      event: '',
      name: '',
      span_id: '',
      trace_id: '',
    })
    expect(result.current.events).toHaveLength(1)
    expect(result.current.summary.returned).toBe(1)
    expect(result.current.dashboardCards).toHaveLength(2)
    expect(result.current.panelTemplates).toHaveLength(1)
    expect(result.current.exportPreview?.service_name).toBe('insightdesk')
    expect(result.current.latestTimestamp).not.toBe('-')
  })

  it('applies trimmed filters through the trace request', async () => {
    mocks.getTraceEvents.mockResolvedValue(traceResponse())

    const { result } = renderHook(() => useTraceOperationsPanel())

    await waitFor(() => expect(mocks.getTraceEvents).toHaveBeenCalledTimes(1))

    act(() => {
      result.current.setEventFilter('error')
      result.current.setNameFilter(' fetch-users ')
      result.current.setTraceIdFilter(' trace-1 ')
      result.current.setSpanIdFilter(' span-1 ')
    })
    act(() => {
      result.current.handleApplyFilters()
    })

    await waitFor(() => expect(mocks.getTraceEvents).toHaveBeenCalledTimes(2))

    expect(mocks.getTraceEvents).toHaveBeenLastCalledWith(100, {
      event: 'error',
      name: 'fetch-users',
      span_id: 'span-1',
      trace_id: 'trace-1',
    })
    expect(result.current.filtersActive).toBe(true)
    expect(result.current.canResetFilters).toBe(true)
  })

  it('clears traces and exposes a success notice', async () => {
    mocks.getTraceEvents.mockResolvedValue(traceResponse())
    mocks.clearTraceEvents.mockResolvedValue({ ok: true, cleared: true })

    const { result } = renderHook(() => useTraceOperationsPanel())

    await waitFor(() => expect(result.current.events).toHaveLength(1))

    await act(async () => {
      await result.current.handleClear()
    })

    expect(mocks.clearTraceEvents).toHaveBeenCalledTimes(1)
    expect(result.current.events).toEqual([])
    expect(result.current.summary.returned).toBe(0)
    expect(result.current.notice).toBe('Trace cleared')
  })
})
