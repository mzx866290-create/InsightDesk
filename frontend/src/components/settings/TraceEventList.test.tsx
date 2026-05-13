import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { TraceEvent } from '../../api/client'
import { TraceEventList } from './TraceEventList'
import { clampText } from './traceOperationsModel'

const event = (patch: Partial<TraceEvent> = {}): TraceEvent => ({
  event: 'error',
  name: 'fetch-users',
  trace_id: 'trace-1234567890',
  span_id: 'span-1234567890',
  parent_span_id: null,
  timestamp: 1_715_000_000,
  duration_ms: 123.4,
  attributes: { status: 'failed', retry: 2 },
  error_type: 'TimeoutError',
  error_message: 'request timed out',
  process_id: 'proc-1',
  source: 'trace',
  ...patch,
})

describe('TraceEventList', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('renders loading and empty states', () => {
    const { rerender } = render(<TraceEventList events={[]} loading />)

    expect(document.querySelector('.animate-spin')).toBeInTheDocument()
    expect(screen.queryByTestId('settings-trace-empty')).not.toBeInTheDocument()

    rerender(<TraceEventList events={[]} loading={false} />)

    expect(screen.getByTestId('settings-trace-empty')).toHaveTextContent('暂无 Trace。')
  })

  it('renders a row with event, time, duration and attributes', () => {
    render(<TraceEventList events={[event()]} loading={false} />)

    const row = screen.getByTestId('settings-trace-event-row')
    expect(within(row).getByText('fetch-users')).toBeInTheDocument()
    expect(within(row).getByText('error')).toHaveClass('bg-accent-red/15')
    expect(within(row).getByText('123.4 ms')).toBeInTheDocument()
    expect(within(row).getByText('TimeoutError: request timed out')).toBeInTheDocument()
    expect(within(row).getByText('status=failed | retry=2')).toBeInTheDocument()
    expect(
      within(row).getAllByText((_, element) =>
        element?.tagName === 'P' &&
        element.textContent === 'trace-12 / span-123 | 2024/5/6 20:53:20',
      ),
    ).toHaveLength(1)
  })

  it('clamps long error and attribute text', () => {
    const longText = 'x'.repeat(180)

    render(
      <TraceEventList
        events={[event({
          error_type: longText,
          error_message: longText,
          attributes: { note: longText },
        })]}
        loading={false}
      />,
    )

    const row = screen.getByTestId('settings-trace-event-row')
    const titleNodes = within(row).getAllByTitle(`${longText}: ${longText}`)
    expect(titleNodes[0]).toBeInTheDocument()
    expect(within(row).getByTitle(`note=${clampText(longText, 48)}`)).toHaveTextContent(/\.\.\.$/)
  })
})
