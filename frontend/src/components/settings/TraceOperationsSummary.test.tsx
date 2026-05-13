import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { TraceSummary } from '../../api/client'
import { TraceOperationsSummary } from './TraceOperationsSummary'

const summary: TraceSummary = {
  returned: 12,
  limit: 50,
  error_events: 3,
  filters: {
    event: '',
    name: '',
    trace_id: '',
    span_id: '',
  },
}

describe('TraceOperationsSummary', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders returned count, errors and latest timestamp', () => {
    render(
      <TraceOperationsSummary
        filtersActive={false}
        latestTimestamp="2026/05/08 14:45:00"
        summary={summary}
      />,
    )

    const panel = screen.getByTestId('settings-trace-summary')
    expect(within(panel).getByText((_, element) =>
      element?.tagName === 'SPAN' && element.textContent === '返回：12 / 50',
    )).toBeInTheDocument()
    expect(within(panel).getByText('3')).toHaveClass('text-accent-red')
    expect(within(panel).getByText('2026/05/08 14:45:00')).toBeInTheDocument()
  })

  it('preserves the existing filter status test id', () => {
    const { rerender } = render(
      <TraceOperationsSummary filtersActive={false} latestTimestamp="-" summary={summary} />,
    )

    expect(screen.getByTestId('settings-trace-filter-status')).toHaveTextContent('all')

    rerender(<TraceOperationsSummary filtersActive latestTimestamp="-" summary={summary} />)

    expect(screen.getByTestId('settings-trace-filter-status')).toHaveTextContent('filtered')
  })
})
