import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  McpConnector,
  McpConnectorApprovalsResponse,
} from '../../api/client'
import { McpApprovalsListPanel } from './McpApprovalsListPanel'

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

const connectors: McpConnector[] = [
  {
    name: 'filesystem',
    label: 'Filesystem',
    description: 'Local files',
    category: 'local',
    builtin: true,
    transport: 'stdio',
    source: 'catalog',
    risk_level: 'high',
    enabled: true,
    configured: true,
    healthy: true,
    requires_approval: true,
  },
]

const approvals: McpConnectorApprovalsResponse = {
  approved_connectors: [],
  runtime_connectors: [],
  env_connectors: [],
  persisted_connectors: [],
  sources: {
    filesystem: ['catalog'],
  },
  persistence: { enabled: true, config_key: 'mcp.runtime.approvals' },
  total: 0,
}

describe('McpApprovalsListPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders empty and loading states', () => {
    const { rerender } = render(
      <McpApprovalsListPanel
        connectors={[]}
        approvals={approvals}
        actingName={null}
        loading={false}
        onApprove={vi.fn()}
        onRevoke={vi.fn()}
      />,
    )

    expect(screen.getByTestId('settings-mcp-approvals-empty')).toHaveTextContent('No MCP connectors.')

    rerender(
      <McpApprovalsListPanel
        connectors={[]}
        approvals={approvals}
        actingName={null}
        loading
        onApprove={vi.fn()}
        onRevoke={vi.fn()}
      />,
    )

    expect(screen.queryByTestId('settings-mcp-approvals-empty')).not.toBeInTheDocument()
  })

  it('renders connector rows and forwards approve action', () => {
    const onApprove = vi.fn()

    render(
      <McpApprovalsListPanel
        connectors={connectors}
        approvals={approvals}
        actingName={null}
        loading={false}
        onApprove={onApprove}
        onRevoke={vi.fn()}
      />,
    )

    expect(screen.getByTestId('settings-mcp-approvals-list')).toHaveTextContent('Filesystem')
    fireEvent.click(screen.getByTestId('settings-mcp-approve-filesystem'))
    expect(onApprove).toHaveBeenCalledWith('filesystem')
  })
})
