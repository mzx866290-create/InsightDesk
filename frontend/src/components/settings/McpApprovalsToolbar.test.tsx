import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { McpApprovalsToolbar } from './McpApprovalsToolbar'

vi.mock('../ui/Button', () => ({
  Button: ({
    children,
    loading: _loading,
    variant: _variant,
    size: _size,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    loading?: boolean
    variant?: string
    size?: string
  }) => <button {...props}>{children}</button>,
}))

describe('McpApprovalsToolbar', () => {
  afterEach(() => {
    cleanup()
  })

  it('forwards runtime check and refresh actions', () => {
    const onRuntimeHealth = vi.fn()
    const onRefresh = vi.fn()

    render(
      <McpApprovalsToolbar
        checkingRuntime={false}
        loading={false}
        onRuntimeHealth={onRuntimeHealth}
        onRefresh={onRefresh}
      />,
    )

    fireEvent.click(screen.getByTestId('settings-mcp-runtime-health-check'))
    fireEvent.click(screen.getByTestId('settings-mcp-approvals-refresh'))

    expect(onRuntimeHealth).toHaveBeenCalledTimes(1)
    expect(onRefresh).toHaveBeenCalledTimes(1)
  })
})
