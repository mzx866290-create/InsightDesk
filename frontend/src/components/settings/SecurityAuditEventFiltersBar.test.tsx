import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { SecurityAuditEventFiltersBar } from './SecurityAuditEventFiltersBar'

function renderBar(overrides: Partial<React.ComponentProps<typeof SecurityAuditEventFiltersBar>> = {}) {
  const props: React.ComponentProps<typeof SecurityAuditEventFiltersBar> = {
    eventsCount: 2,
    eventsTotal: 10,
    eventsLimit: 200,
    actionFilter: '',
    resultFilter: '',
    categoryFilter: '',
    userFilter: '',
    sinceFilter: '',
    untilFilter: '',
    resultOptions: ['blocked', 'allowed'],
    loading: false,
    resetDisabled: false,
    onActionFilterChange: vi.fn(),
    onResultFilterChange: vi.fn(),
    onCategoryFilterChange: vi.fn(),
    onUserFilterChange: vi.fn(),
    onSinceFilterChange: vi.fn(),
    onUntilFilterChange: vi.fn(),
    onApplyFilters: vi.fn(),
    onResetFilters: vi.fn(),
    onRefresh: vi.fn(),
    ...overrides,
  }

  return {
    props,
    ...render(<SecurityAuditEventFiltersBar {...props} />),
  }
}

describe('SecurityAuditEventFiltersBar', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders event totals and result/category options', () => {
    renderBar()

    expect(screen.getByTestId('settings-security-audit-event-filters')).toHaveTextContent(
      'Events (2 / 10, limit 200)',
    )
    expect(screen.getByRole('option', { name: 'blocked' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'allowed' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Auth' })).toBeInTheDocument()
  })

  it('emits filter changes and applies on button or Enter', () => {
    const onActionFilterChange = vi.fn()
    const onUserFilterChange = vi.fn()
    const onApplyFilters = vi.fn()

    renderBar({ onActionFilterChange, onUserFilterChange, onApplyFilters })

    fireEvent.change(screen.getByTestId('settings-security-audit-event-action-filter'), {
      target: { value: 'remote_auth_guard' },
    })
    fireEvent.change(screen.getByTestId('settings-security-audit-event-user-filter'), {
      target: { value: 'user-1' },
    })
    fireEvent.keyDown(screen.getByTestId('settings-security-audit-event-user-filter'), { key: 'Enter' })
    fireEvent.click(screen.getByTestId('settings-security-audit-event-apply-filters'))

    expect(onActionFilterChange).toHaveBeenCalledWith('remote_auth_guard')
    expect(onUserFilterChange).toHaveBeenCalledWith('user-1')
    expect(onApplyFilters).toHaveBeenCalledTimes(2)
  })

  it('resets and refreshes through stable actions', () => {
    const onResetFilters = vi.fn()
    const onRefresh = vi.fn()

    renderBar({ resetDisabled: false, onResetFilters, onRefresh })

    fireEvent.click(screen.getByTestId('settings-security-audit-event-reset-filters'))
    fireEvent.click(screen.getByTestId('settings-security-audit-event-refresh'))

    expect(onResetFilters).toHaveBeenCalledTimes(1)
    expect(onRefresh).toHaveBeenCalledTimes(1)
  })

  it('disables reset when there are no draft or applied filters', () => {
    renderBar({ resetDisabled: true })

    expect(screen.getByTestId('settings-security-audit-event-reset-filters')).toBeDisabled()
  })
})
