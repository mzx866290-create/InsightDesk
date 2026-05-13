import React from 'react'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { McpRuntimeHealthResponse } from '../../api/client'
import type { McpMarketplaceSummaryView } from './mcpMarketplaceModel'
import { McpProductizationSummaryPanel } from './McpProductizationSummaryPanel'

const marketplaceSummary: McpMarketplaceSummaryView = {
  total: 4,
  enabled: 3,
  healthy: 2,
  approval: 1,
  builtin: 2,
  custom: 2,
  categories: 3,
}

const runtimeHealth = (patch: Partial<McpRuntimeHealthResponse> = {}): McpRuntimeHealthResponse => ({
  status: 'degraded',
  servers: [],
  history: [],
  history_limit: 10,
  summary: {
    total: 4,
    healthy: 2,
    unhealthy: 2,
    tool_count: 9,
    status_counts: { healthy: 2, degraded: 2 },
    alert_count: 2,
    unhealthy_connectors: ['github', 'filesystem'],
    slow_connectors: [],
  },
  ...patch,
})

describe('McpProductizationSummaryPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders marketplace summary and runtime health text', () => {
    render(
      <McpProductizationSummaryPanel
        marketplaceSummary={marketplaceSummary}
        runtimeHealth={runtimeHealth()}
      />,
    )

    expect(screen.getByText('Total:')).toBeInTheDocument()
    expect(screen.getByText('Enabled:')).toBeInTheDocument()
    expect(screen.getByText('Approval:')).toBeInTheDocument()
    expect(screen.getByTestId('settings-mcp-runtime-status')).toHaveTextContent('degraded')
    expect(screen.getByTestId('settings-mcp-runtime-summary')).toHaveTextContent('Healthy: 2')
    expect(screen.getByTestId('settings-mcp-runtime-summary')).toHaveTextContent('Tools: 9')
  })

  it('renders runtime alert when alert count is present', () => {
    render(
      <McpProductizationSummaryPanel
        marketplaceSummary={marketplaceSummary}
        runtimeHealth={runtimeHealth()}
      />,
    )

    expect(screen.getByTestId('settings-mcp-runtime-alert')).toHaveTextContent('Runtime alerts: 2')
    expect(screen.getByTestId('settings-mcp-runtime-alert')).toHaveTextContent('github, filesystem')
  })

  it('omits runtime summary and alert when runtime health is unavailable', () => {
    render(
      <McpProductizationSummaryPanel
        marketplaceSummary={marketplaceSummary}
        runtimeHealth={null}
      />,
    )

    expect(screen.getByTestId('settings-mcp-runtime-status')).toHaveTextContent('-')
    expect(screen.queryByTestId('settings-mcp-runtime-summary')).not.toBeInTheDocument()
    expect(screen.queryByTestId('settings-mcp-runtime-alert')).not.toBeInTheDocument()
  })
})
