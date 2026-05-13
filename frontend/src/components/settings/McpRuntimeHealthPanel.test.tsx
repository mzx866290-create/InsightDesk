import React from 'react'
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { McpRuntimeHealthResponse } from '../../api/client'
import { McpRuntimeHealthPanel } from './McpRuntimeHealthPanel'

const summary = {
  total: 1,
  healthy: 1,
  unhealthy: 0,
  tool_count: 2,
  status_counts: { healthy: 1 },
  alert_count: 0,
  unhealthy_connectors: [],
  slow_connectors: [],
}

const runtimeHealth = (patch: Partial<McpRuntimeHealthResponse> = {}): McpRuntimeHealthResponse => ({
  status: 'healthy',
  summary,
  servers: [
    {
      name: 'kb',
      status: 'healthy',
      healthy: true,
      tool_count: 2,
      tools: ['search', 'retrieve'],
      duration_ms: 8.456,
      error: null,
    },
  ],
  history: [],
  history_limit: 10,
  ...patch,
})

describe('McpRuntimeHealthPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('does not render before a runtime health check exists', () => {
    const { container } = render(
      <McpRuntimeHealthPanel
        runtimeHealth={null}
        connectorLabelByName={new Map()}
      />,
    )

    expect(container).toBeEmptyDOMElement()
  })

  it('renders summary and server rows with connector labels', () => {
    render(
      <McpRuntimeHealthPanel
        runtimeHealth={runtimeHealth()}
        connectorLabelByName={new Map([['kb', 'Knowledge Base']])}
      />,
    )

    const panel = screen.getByTestId('settings-mcp-runtime-health')
    expect(within(panel).getAllByText('healthy')).toHaveLength(2)
    expect(within(panel).getByText('1')).toHaveClass('text-accent-green')
    expect(within(panel).getByText('2')).toHaveClass('text-text-primary')

    const row = screen.getByTestId('settings-mcp-runtime-health-row')
    expect(row).toHaveAttribute('data-connector-name', 'kb')
    expect(within(row).getByText('Knowledge Base')).toBeInTheDocument()
    expect(within(row).getByText('healthy')).toHaveClass('text-accent-green')
    expect(within(row).getByText('8.46 ms')).toBeInTheDocument()
    expect(within(row).getByText('search, retrieve')).toHaveAttribute('title', 'search, retrieve')
  })

  it('renders server errors and empty runtime state', () => {
    const { rerender } = render(
      <McpRuntimeHealthPanel
        runtimeHealth={runtimeHealth({
          status: 'degraded',
          summary: { ...summary, healthy: 0, unhealthy: 1 },
          servers: [
            {
              name: 'unknown',
              status: 'failed',
              healthy: false,
              tool_count: 0,
              tools: [],
              duration_ms: 12,
              error: 'connection refused',
            },
          ],
        })}
        connectorLabelByName={new Map()}
      />,
    )

    const row = screen.getByTestId('settings-mcp-runtime-health-row')
    expect(within(row).getByText('unknown')).toBeInTheDocument()
    expect(within(row).getByText('failed')).toHaveClass('text-accent-red')
    expect(within(row).getByText('12.0 ms')).toBeInTheDocument()
    expect(within(row).getByText('connection refused')).toHaveAttribute('title', 'connection refused')

    rerender(
      <McpRuntimeHealthPanel
        runtimeHealth={runtimeHealth({ servers: [] })}
        connectorLabelByName={new Map()}
      />,
    )

    expect(screen.getByTestId('settings-mcp-runtime-health-empty')).toHaveTextContent('No active runtime connectors.')
  })
})
