import React from 'react'

import type { McpRuntimeHealthResponse } from '../../api/client'
import type { McpMarketplaceSummaryView } from './mcpMarketplaceModel'

interface McpProductizationSummaryPanelProps {
  marketplaceSummary: McpMarketplaceSummaryView
  runtimeHealth: McpRuntimeHealthResponse | null
}

export const McpProductizationSummaryPanel: React.FC<McpProductizationSummaryPanelProps> = ({
  marketplaceSummary,
  runtimeHealth,
}) => {
  return (
    <>
      <div className="mt-3 grid gap-2 rounded-lg border border-bg-border bg-bg-secondary/30 px-3 py-2 text-[11px] text-text-secondary sm:grid-cols-4 xl:grid-cols-8">
        <span>Total: <b className="text-text-primary">{marketplaceSummary.total}</b></span>
        <span>Enabled: <b className="text-text-primary">{marketplaceSummary.enabled}</b></span>
        <span>Healthy: <b className="text-text-primary">{marketplaceSummary.healthy}</b></span>
        <span>Approval: <b className="text-text-primary">{marketplaceSummary.approval}</b></span>
        <span>Builtin: <b className="text-text-primary">{marketplaceSummary.builtin}</b></span>
        <span>Custom: <b className="text-text-primary">{marketplaceSummary.custom}</b></span>
        <span>Categories: <b className="text-text-primary">{marketplaceSummary.categories}</b></span>
        <span>
          Runtime:{' '}
          <b className="text-text-primary" data-testid="settings-mcp-runtime-status">
            {runtimeHealth?.status ?? '-'}
          </b>
        </span>
      </div>

      {runtimeHealth && (
        <div
          className="mt-3 grid gap-2 rounded-lg border border-bg-border bg-bg-tertiary/30 px-3 py-2 text-[11px] text-text-secondary sm:grid-cols-4"
          data-testid="settings-mcp-runtime-summary"
        >
          <span>Healthy: <b className="text-text-primary">{runtimeHealth.summary.healthy}</b></span>
          <span>Unhealthy: <b className="text-text-primary">{runtimeHealth.summary.unhealthy}</b></span>
          <span>Alerts: <b className="text-text-primary">{runtimeHealth.summary.alert_count}</b></span>
          <span>Tools: <b className="text-text-primary">{runtimeHealth.summary.tool_count}</b></span>
        </div>
      )}

      {runtimeHealth?.summary.alert_count ? (
        <div
          className="mt-3 rounded-lg border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-xs text-amber-200"
          data-testid="settings-mcp-runtime-alert"
        >
          Runtime alerts: {runtimeHealth.summary.alert_count}. Unhealthy:{' '}
          {runtimeHealth.summary.unhealthy_connectors.join(', ') || '-'}
        </div>
      ) : null}
    </>
  )
}
