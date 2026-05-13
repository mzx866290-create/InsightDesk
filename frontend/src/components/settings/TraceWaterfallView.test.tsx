import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { TraceEvent } from '../../api/client'
import { TraceWaterfallView } from './TraceWaterfallView'

const event = (patch: Partial<TraceEvent>): TraceEvent => ({
  event: 'end',
  name: 'llm.invoke',
  trace_id: 'trace-1234567890',
  span_id: 'span-1234567890',
  parent_span_id: null,
  timestamp: 1_715_000_000,
  duration_ms: 120,
  attributes: {},
  error_type: null,
  error_message: null,
  ...patch,
})

describe('TraceWaterfallView', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders nothing without events after loading finishes', () => {
    const { container } = render(<TraceWaterfallView events={[]} loading={false} />)

    expect(container.firstChild).toBeNull()
  })

  it('renders grouped waterfall rows', () => {
    render(
      <TraceWaterfallView
        loading={false}
        events={[
          event({ span_id: 'root-1234567890', name: 'llm.invoke', duration_ms: 500 }),
          event({
            event: 'error',
            span_id: 'child-1234567890',
            parent_span_id: 'root-1234567890',
            name: 'tool.execute',
            timestamp: 1_715_000_000.1,
            duration_ms: 100,
            error_type: 'ToolError',
            error_message: 'boom',
          }),
        ]}
      />,
    )

    const waterfall = screen.getByTestId('settings-trace-waterfall')
    const rows = within(waterfall).getAllByTestId('settings-trace-waterfall-row')

    expect(within(waterfall).getByText('trace trace-12')).toBeInTheDocument()
    expect(rows).toHaveLength(2)
    expect(within(rows[0]).getByText('llm.invoke')).toBeInTheDocument()
    expect(within(rows[1]).getByText(/tool\.execute/)).toBeInTheDocument()
    expect(within(rows[1]).getByText('ToolError: boom')).toBeInTheDocument()
  })
})
