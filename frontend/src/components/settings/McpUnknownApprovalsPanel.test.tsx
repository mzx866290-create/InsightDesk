import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { McpUnknownApprovalsPanel } from './McpUnknownApprovalsPanel'

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

describe('McpUnknownApprovalsPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders nothing without unknown connectors', () => {
    const { container } = render(
      <McpUnknownApprovalsPanel
        connectorNames={[]}
        actingName={null}
        onRevoke={vi.fn()}
      />,
    )

    expect(container).toBeEmptyDOMElement()
  })

  it('renders unknown approvals and forwards revoke action', () => {
    const onRevoke = vi.fn()

    render(
      <McpUnknownApprovalsPanel
        connectorNames={['legacy_tool']}
        actingName={null}
        onRevoke={onRevoke}
      />,
    )

    expect(screen.getByText('Runtime approvals outside the current catalog')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('settings-mcp-revoke-legacy_tool'))
    expect(onRevoke).toHaveBeenCalledWith('legacy_tool')
  })
})
