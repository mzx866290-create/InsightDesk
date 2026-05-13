import React from 'react'

import type { McpRuntimeHealthResponse } from '../../api/client'
import { statusClass } from './mcpApprovalsModel'

interface McpRuntimeHealthPanelProps {
  runtimeHealth: McpRuntimeHealthResponse | null
  connectorLabelByName: Map<string, string>
}

export const McpRuntimeHealthPanel: React.FC<McpRuntimeHealthPanelProps> = ({
  runtimeHealth,
  connectorLabelByName,
}) => {
  if (!runtimeHealth) return null

  return (
    <div
      className="space-y-2 rounded-lg border border-bg-border bg-bg-tertiary/30 p-3"
      data-testid="settings-mcp-runtime-health"
    >
      <div className="grid gap-2 text-xs text-text-secondary sm:grid-cols-4">
        <span>Status: <b className="text-text-primary">{runtimeHealth.status}</b></span>
        <span>Healthy: <b className="text-accent-green">{runtimeHealth.summary.healthy}</b></span>
        <span>Unhealthy: <b className="text-accent-red">{runtimeHealth.summary.unhealthy}</b></span>
        <span>Tools: <b className="text-text-primary">{runtimeHealth.summary.tool_count}</b></span>
      </div>
      <div className="overflow-hidden rounded-md border border-bg-border">
        {runtimeHealth.servers.length === 0 ? (
          <div className="px-3 py-3 text-xs text-text-secondary" data-testid="settings-mcp-runtime-health-empty">
            No active runtime connectors.
          </div>
        ) : (
          runtimeHealth.servers.map((server) => (
            <div
              key={server.name}
              className="grid gap-2 border-t border-bg-border px-3 py-2 text-xs text-text-secondary first:border-t-0 md:grid-cols-[minmax(10rem,1fr)_6rem_5rem_minmax(12rem,1fr)]"
              data-testid="settings-mcp-runtime-health-row"
              data-connector-name={server.name}
            >
              <span className="font-medium text-text-primary">
                {connectorLabelByName.get(server.name) ?? server.name}
              </span>
              <span className={statusClass(server.healthy)}>{server.status}</span>
              <span>{server.duration_ms.toFixed(server.duration_ms >= 10 ? 1 : 2)} ms</span>
              <span className="min-w-0 truncate" title={server.error ?? server.tools.join(', ')}>
                {server.error ?? (server.tools.length > 0 ? server.tools.join(', ') : '-')}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
