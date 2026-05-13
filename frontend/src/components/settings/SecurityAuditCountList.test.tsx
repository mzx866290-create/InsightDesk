import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { SecurityAuditCountList } from './SecurityAuditCountList'

describe('SecurityAuditCountList', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders an empty state when there are no positive counts', () => {
    render(
      <SecurityAuditCountList
        title="Actions"
        counts={{ skipped: 0 }}
        kind="action"
        emptyText="No actions in this window."
        testId="security-count-list"
      />,
    )

    expect(screen.getByTestId('security-count-list')).toHaveTextContent('No actions in this window.')
    expect(screen.queryByTestId('security-count-list-row')).not.toBeInTheDocument()
  })

  it('sorts counts, highlights selected rows, and forwards row clicks', () => {
    const onSelectName = vi.fn()

    render(
      <SecurityAuditCountList
        title="Results"
        counts={{ blocked: 2, allowed: 4, denied: 2 }}
        kind="result"
        emptyText="No results in this window."
        testId="security-count-list"
        selectedName="blocked"
        onSelectName={onSelectName}
      />,
    )

    const rows = screen.getAllByTestId('security-count-list-row')
    expect(rows).toHaveLength(3)
    expect(within(rows[0]).getByText('allowed')).toBeInTheDocument()
    expect(within(rows[0]).getByText('4')).toHaveClass('text-accent-green')
    expect(within(rows[1]).getByText('blocked')).toBeInTheDocument()
    expect(rows[1]).toHaveClass('bg-accent-blue/10')
    expect(within(rows[1]).getByText('2')).toHaveClass('text-accent-red')

    fireEvent.click(rows[2])
    expect(onSelectName).toHaveBeenCalledWith('denied')
  })
})
