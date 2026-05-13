import React from 'react'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { McpApprovalsMessage } from './McpApprovalsMessage'

describe('McpApprovalsMessage', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders nothing without error or notice', () => {
    const { container } = render(<McpApprovalsMessage error={null} notice={null} />)

    expect(container).toBeEmptyDOMElement()
  })

  it('prefers error over notice', () => {
    render(<McpApprovalsMessage error="Load failed" notice="Config saved" />)

    expect(screen.getByTestId('settings-mcp-approvals-message')).toHaveTextContent('Load failed')
    expect(screen.getByTestId('settings-mcp-approvals-message')).toHaveClass('text-accent-red')
  })

  it('renders notice state', () => {
    render(<McpApprovalsMessage error={null} notice="Config saved" />)

    expect(screen.getByTestId('settings-mcp-approvals-message')).toHaveTextContent('Config saved')
    expect(screen.getByTestId('settings-mcp-approvals-message')).toHaveClass('text-accent-green')
  })
})
