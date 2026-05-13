import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { SecurityAuditToolbar } from './SecurityAuditToolbar'

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
  }) => (
    <button {...props}>{children}</button>
  ),
}))

describe('SecurityAuditToolbar', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders category and limit controls and forwards changes', () => {
    const onCategoryChange = vi.fn()
    const onLimitChange = vi.fn()
    const onRefresh = vi.fn()

    render(
      <SecurityAuditToolbar
        category="all"
        limit={200}
        loading={false}
        onCategoryChange={onCategoryChange}
        onLimitChange={onLimitChange}
        onRefresh={onRefresh}
      />,
    )

    fireEvent.change(screen.getByTestId('settings-security-audit-category'), {
      target: { value: 'auth' },
    })
    fireEvent.change(screen.getByTestId('settings-security-audit-limit'), {
      target: { value: '500' },
    })
    fireEvent.click(screen.getByTestId('settings-security-audit-refresh'))

    expect(onCategoryChange).toHaveBeenCalledWith('auth')
    expect(onLimitChange).toHaveBeenCalledWith(500)
    expect(onRefresh).toHaveBeenCalledTimes(1)
  })
})
