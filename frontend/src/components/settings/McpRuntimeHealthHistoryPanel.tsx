import React from 'react'
import { RefreshCw } from 'lucide-react'

import type { McpRuntimeHealthHistoryItem } from '../../api/client'
import { Button } from '../ui/Button'
import { formatRuntimeHistoryTimestamp, statusClass } from './mcpApprovalsModel'

interface McpRuntimeHealthHistoryPanelProps {
  history: McpRuntimeHealthHistoryItem[]
  loading: boolean
  error: string | null
  onRefresh: () => void
  connectorLabelByName: Map<string, string>
}

export const McpRuntimeHealthHistoryPanel: React.FC<McpRuntimeHealthHistoryPanelProps> = ({
  history,
  loading,
  error,
  onRefresh,
  connectorLabelByName,
}) => (
  <div
    className="space-y-2 rounded-lg border border-bg-border bg-bg-tertiary/30 p-3"
    data-testid="settings-mcp-runtime-health-history"
  >
    <div className="flex items-center justify-between gap-2">
      <p className="text-[11px] font-medium uppercase tracking-wide text-text-secondary">
        Runtime health history
      </p>
      <Button
        variant="ghost"
        size="sm"
        onClick={onRefresh}
        loading={loading}
        data-testid="settings-mcp-runtime-health-history-refresh"
      >
        <RefreshCw size={12} />
        Refresh
      </Button>
    </div>
    {error ? (
      <div className="rounded-md border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red">
        {error}
      </div>
    ) : loading && history.length === 0 ? (
      <div className="px-3 py-3 text-xs text-text-secondary">
        Loading runtime health history...
      </div>
    ) : history.length === 0 ? (
      <div className="px-3 py-3 text-xs text-text-secondary">
        No runtime health history.
      </div>
    ) : (
      <div className="space-y-1 rounded-md border border-bg-border bg-bg-tertiary/20 px-3 py-2">
        {history.map((item) => {
          const connectorNames = item.servers
            .map((server) => connectorLabelByName.get(server.name) ?? server.name)
            .filter(Boolean)
          const connectorSummary = connectorNames.length > 0
            ? connectorNames.join(', ')
            : formatRuntimeHistoryTimestamp(item.timestamp)
          const historyHealthy = item.summary.unhealthy === 0
          return (
            <div
              key={`${item.timestamp}-${item.status}`}
              className="grid gap-1 text-[11px] text-text-secondary md:grid-cols-[7rem_9rem_5rem_minmax(12rem,1fr)]"
              data-testid="settings-mcp-runtime-health-history-row"
            >
              <span className={statusClass(historyHealthy)}>{item.status}</span>
              <span>{item.summary.healthy} healthy / {item.summary.unhealthy} unhealthy</span>
              <span>alerts {item.summary.alert_count}</span>
              <span className="min-w-0 truncate" title={connectorSummary}>
                {connectorSummary}
              </span>
            </div>
          )
        })}
      </div>
    )}
  </div>
)
