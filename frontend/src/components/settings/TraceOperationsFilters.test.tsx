import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  TraceOperationsFilters,
  type TraceOperationsFiltersProps,
} from './TraceOperationsFilters'

vi.mock('../ui/Button', () => ({
  Button: ({
    children,
    loading,
    disabled,
    variant: _variant,
    size: _size,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    loading?: boolean
    variant?: string
    size?: string
  }) => (
    <button {...props} disabled={disabled || loading} data-loading={loading ? 'true' : 'false'}>
      {children}
    </button>
  ),
}))

function createProps(overrides: Partial<TraceOperationsFiltersProps> = {}): TraceOperationsFiltersProps {
  return {
    eventFilter: '',
    nameFilter: '',
    traceIdFilter: '',
    spanIdFilter: '',
    loading: false,
    canResetFilters: false,
    onEventFilterChange: vi.fn(),
    onNameFilterChange: vi.fn(),
    onTraceIdFilterChange: vi.fn(),
    onSpanIdFilterChange: vi.fn(),
    onApplyFilters: vi.fn(),
    onResetFilters: vi.fn(),
    ...overrides,
  }
}

describe('TraceOperationsFilters', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('preserves filter test ids and displays controlled values', () => {
    render(
      <TraceOperationsFilters
        {...createProps({
          eventFilter: 'error',
          nameFilter: 'fetch-users',
          traceIdFilter: 'trace-123',
          spanIdFilter: 'span-456',
          canResetFilters: true,
        })}
      />,
    )

    expect(screen.getByTestId('settings-trace-filter-event')).toHaveValue('error')
    expect(screen.getByTestId('settings-trace-filter-name')).toHaveValue('fetch-users')
    expect(screen.getByTestId('settings-trace-filter-trace-id')).toHaveValue('trace-123')
    expect(screen.getByTestId('settings-trace-filter-span-id')).toHaveValue('span-456')
    expect(screen.getByTestId('settings-trace-apply-filters')).toBeEnabled()
    expect(screen.getByTestId('settings-trace-reset-filters')).toBeEnabled()
  })

  it('forwards filter field changes', () => {
    const props = createProps()

    render(<TraceOperationsFilters {...props} />)

    fireEvent.change(screen.getByTestId('settings-trace-filter-event'), {
      target: { value: 'start' },
    })
    fireEvent.change(screen.getByTestId('settings-trace-filter-name'), {
      target: { value: 'span-name' },
    })
    fireEvent.change(screen.getByTestId('settings-trace-filter-trace-id'), {
      target: { value: 'trace-id' },
    })
    fireEvent.change(screen.getByTestId('settings-trace-filter-span-id'), {
      target: { value: 'span-id' },
    })

    expect(props.onEventFilterChange).toHaveBeenCalledWith('start')
    expect(props.onNameFilterChange).toHaveBeenCalledWith('span-name')
    expect(props.onTraceIdFilterChange).toHaveBeenCalledWith('trace-id')
    expect(props.onSpanIdFilterChange).toHaveBeenCalledWith('span-id')
  })

  it('applies filters from the apply button and Enter key', () => {
    const props = createProps()

    render(<TraceOperationsFilters {...props} />)

    fireEvent.click(screen.getByTestId('settings-trace-apply-filters'))
    fireEvent.keyDown(screen.getByTestId('settings-trace-filter-name'), { key: 'Enter' })
    fireEvent.keyDown(screen.getByTestId('settings-trace-filter-trace-id'), { key: 'Enter' })
    fireEvent.keyDown(screen.getByTestId('settings-trace-filter-span-id'), { key: 'Enter' })
    fireEvent.keyDown(screen.getByTestId('settings-trace-filter-name'), { key: 'Escape' })

    expect(props.onApplyFilters).toHaveBeenCalledTimes(4)
  })

  it('keeps reset disabled until filters can reset and disables apply while loading', () => {
    const props = createProps({ loading: true, canResetFilters: false })
    const { rerender } = render(<TraceOperationsFilters {...props} />)

    expect(screen.getByTestId('settings-trace-apply-filters')).toBeDisabled()
    expect(screen.getByTestId('settings-trace-reset-filters')).toBeDisabled()

    const activeProps = createProps({ canResetFilters: true })
    rerender(<TraceOperationsFilters {...activeProps} />)

    fireEvent.click(screen.getByTestId('settings-trace-reset-filters'))

    expect(screen.getByTestId('settings-trace-reset-filters')).toBeEnabled()
    expect(activeProps.onResetFilters).toHaveBeenCalledTimes(1)
  })
})
