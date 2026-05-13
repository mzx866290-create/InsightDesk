import React from 'react'
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { McpConnectorApprovalsResponse } from '../../api/client'
import { McpApprovalsSummaryPanel } from './McpApprovalsSummaryPanel'

const approvals = (patch: Partial<McpConnectorApprovalsResponse> = {}): McpConnectorApprovalsResponse => ({
  approved_connectors: ['kb', 'search'],
  env_connectors: ['kb'],
  runtime_connectors: ['search'],
  persisted_connectors: [],
  sources: {},
  persistence: { enabled: true, config_key: 'mcp.connectors' },
  total: 2,
  ...patch,
})

describe('McpApprovalsSummaryPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders effective, runtime, env, and store summaries', () => {
    render(<McpApprovalsSummaryPanel approvals={approvals()} />)

    const panel = screen.getByTestId('settings-mcp-approvals-summary')
    expect(within(panel).getByTestId('settings-mcp-approvals-summary-effective')).toHaveTextContent('Effective: 2')
    expect(within(panel).getByTestId('settings-mcp-approvals-summary-runtime')).toHaveTextContent('Runtime: 1')
    expect(within(panel).getByTestId('settings-mcp-approvals-summary-env')).toHaveTextContent('Env: 1')
    expect(within(panel).getByTestId('settings-mcp-approvals-summary-store')).toHaveTextContent('Store: mcp.connectors')
  })

  it('renders a dash when persistence is disabled', () => {
    render(
      <McpApprovalsSummaryPanel
        approvals={approvals({
          persistence: { enabled: false, config_key: 'mcp.connectors' },
        })}
      />,
    )

    expect(screen.getByTestId('settings-mcp-approvals-summary-store')).toHaveTextContent('Store: -')
  })
})
