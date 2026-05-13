import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { TraceOperationsToolbar } from './TraceOperationsToolbar'

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

describe('TraceOperationsToolbar', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('preserves toolbar test ids and forwards actions', () => {
    const onClear = vi.fn()
    const onLimitChange = vi.fn()
    const onRefresh = vi.fn()

    render(
      <TraceOperationsToolbar
        clearing={false}
        hasEvents
        limit={100}
        loading={false}
        onClear={onClear}
        onLimitChange={onLimitChange}
        onRefresh={onRefresh}
      />,
    )

    fireEvent.change(screen.getByTestId('settings-trace-limit'), { target: { value: '200' } })
    fireEvent.click(screen.getByTestId('settings-trace-refresh'))
    fireEvent.click(screen.getByTestId('settings-trace-clear'))

    expect(onLimitChange).toHaveBeenCalledWith(200)
    expect(onRefresh).toHaveBeenCalledTimes(1)
    expect(onClear).toHaveBeenCalledTimes(1)
  })

  it('disables clear without events and disables refresh while loading', () => {
    render(
      <TraceOperationsToolbar
        clearing={false}
        hasEvents={false}
        limit={50}
        loading
        onClear={vi.fn()}
        onLimitChange={vi.fn()}
        onRefresh={vi.fn()}
      />,
    )

    expect(screen.getByTestId('settings-trace-refresh')).toBeDisabled()
    expect(screen.getByTestId('settings-trace-clear')).toBeDisabled()
  })
})
