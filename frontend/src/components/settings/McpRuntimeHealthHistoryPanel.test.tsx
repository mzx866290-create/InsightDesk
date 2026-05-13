import React from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { McpRuntimeHealthHistoryItem, McpRuntimeHealthSummary } from '../../api/client'
import { McpRuntimeHealthHistoryPanel } from './McpRuntimeHealthHistoryPanel'

const summary = (patch: Partial<McpRuntimeHealthSummary> = {}): McpRuntimeHealthSummary => ({
  total: 1,
  healthy: 1,
  unhealthy: 0,
  tool_count: 2,
  status_counts: { healthy: 1 },
  alert_count: 0,
  unhealthy_connectors: [],
  slow_connectors: [],
  ...patch,
})

const historyItem = (patch: Partial<McpRuntimeHealthHistoryItem> = {}): McpRuntimeHealthHistoryItem => ({
  timestamp: 1_715_000_000,
  status: 'healthy',
  summary: summary(),
  servers: [
    {
      name: 'kb',
      status: 'healthy',
      healthy: true,
      tool_count: 2,
      duration_ms: 8,
      error: null,
    },
  ],
  ...patch,
})

function renderHistory(overrides: Partial<React.ComponentProps<typeof McpRuntimeHealthHistoryPanel>> = {}) {
  return render(
    <McpRuntimeHealthHistoryPanel
      history={[]}
      loading={false}
      error={null}
      onRefresh={vi.fn()}
      connectorLabelByName={new Map()}
      {...overrides}
    />,
  )
}

describe('McpRuntimeHealthHistoryPanel', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('renders empty, loading, and error states', () => {
    const { rerender } = renderHistory()

    expect(screen.getByText('No runtime health history.')).toBeInTheDocument()

    rerender(
      <McpRuntimeHealthHistoryPanel
        history={[]}
        loading
        error={null}
        onRefresh={vi.fn()}
        connectorLabelByName={new Map()}
      />,
    )
    expect(screen.getByText('Loading runtime health history...')).toBeInTheDocument()

    rerender(
      <McpRuntimeHealthHistoryPanel
        history={[]}
        loading={false}
        error="history unavailable"
        onRefresh={vi.fn()}
        connectorLabelByName={new Map()}
      />,
    )
    expect(screen.getByText('history unavailable')).toHaveClass('text-accent-red')
  })

  it('renders history rows with mapped connector labels and refresh callback', () => {
    const onRefresh = vi.fn()

    renderHistory({
      history: [
        historyItem({
          status: 'degraded',
          summary: summary({ healthy: 1, unhealthy: 1, alert_count: 2 }),
        }),
      ],
      onRefresh,
      connectorLabelByName: new Map([['kb', 'Knowledge Base']]),
    })

    fireEvent.click(screen.getByTestId('settings-mcp-runtime-health-history-refresh'))

    expect(onRefresh).toHaveBeenCalledTimes(1)
    const row = screen.getByTestId('settings-mcp-runtime-health-history-row')
    expect(within(row).getByText('degraded')).toHaveClass('text-accent-red')
    expect(within(row).getByText('1 healthy / 1 unhealthy')).toBeInTheDocument()
    expect(within(row).getByText('alerts 2')).toBeInTheDocument()
    expect(within(row).getByText('Knowledge Base')).toHaveAttribute('title', 'Knowledge Base')
  })

  it('falls back to formatted timestamp when history has no servers', () => {
    vi.spyOn(Date.prototype, 'toLocaleString').mockReturnValue('2026/05/08 14:40')

    renderHistory({
      history: [historyItem({ servers: [] })],
    })

    const row = screen.getByTestId('settings-mcp-runtime-health-history-row')
    expect(within(row).getByText('healthy')).toHaveClass('text-accent-green')
    expect(within(row).getByText('2026/05/08 14:40')).toHaveAttribute('title', '2026/05/08 14:40')
  })
})
