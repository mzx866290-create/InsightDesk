import React from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  McpRuntimeHealthHistoryItem,
  McpRuntimeHealthResponse,
  McpRuntimeHealthSummary,
} from '../../api/client'
import { McpRuntimeSection } from './McpRuntimeSection'

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

const runtimeHealth = (patch: Partial<McpRuntimeHealthResponse> = {}): McpRuntimeHealthResponse => ({
  status: 'healthy',
  summary: summary(),
  servers: [
    {
      name: 'kb',
      status: 'healthy',
      healthy: true,
      tool_count: 2,
      tools: ['search', 'retrieve'],
      duration_ms: 8,
      error: null,
    },
  ],
  history: [],
  history_limit: 10,
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

function renderSection(overrides: Partial<React.ComponentProps<typeof McpRuntimeSection>> = {}) {
  return render(
    <McpRuntimeSection
      runtimeHealth={null}
      runtimeHealthHistory={[]}
      loadingRuntimeHistory={false}
      runtimeHistoryError={null}
      onRuntimeHistoryRefresh={vi.fn()}
      connectorLabelByName={new Map()}
      {...overrides}
    />,
  )
}

describe('McpRuntimeSection', () => {
  afterEach(() => {
    cleanup()
  })

  it('forwards connector labels to runtime health and history panels', () => {
    renderSection({
      runtimeHealth: runtimeHealth(),
      runtimeHealthHistory: [historyItem()],
      connectorLabelByName: new Map([['kb', 'Knowledge Base']]),
    })

    const healthRow = screen.getByTestId('settings-mcp-runtime-health-row')
    expect(within(healthRow).getByText('Knowledge Base')).toBeInTheDocument()

    const historyRow = screen.getByTestId('settings-mcp-runtime-health-history-row')
    expect(within(historyRow).getByText('Knowledge Base')).toHaveAttribute('title', 'Knowledge Base')
  })

  it('forwards runtime history refresh events', () => {
    const onRuntimeHistoryRefresh = vi.fn()

    renderSection({
      runtimeHealthHistory: [historyItem()],
      onRuntimeHistoryRefresh,
    })

    fireEvent.click(screen.getByTestId('settings-mcp-runtime-health-history-refresh'))

    expect(onRuntimeHistoryRefresh).toHaveBeenCalledTimes(1)
  })
})
