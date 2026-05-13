import React from 'react'
import { Activity, RefreshCw, ShieldAlert } from 'lucide-react'

import { Button } from '../ui/Button'

export interface McpApprovalsToolbarProps {
  checkingRuntime: boolean
  loading: boolean
  onRuntimeHealth: () => void
  onRefresh: () => void
}

export const McpApprovalsToolbar: React.FC<McpApprovalsToolbarProps> = ({
  checkingRuntime,
  loading,
  onRuntimeHealth,
  onRefresh,
}) => (
  <div className="flex flex-wrap items-center justify-between gap-3">
    <h3 className="flex items-center gap-2 text-sm font-medium text-text-primary">
      <ShieldAlert size={14} className="text-accent-blue" />
      MCP approvals
    </h3>
    <div className="flex flex-wrap items-center gap-2">
      <Button
        variant="ghost"
        size="sm"
        onClick={onRuntimeHealth}
        loading={checkingRuntime}
        data-testid="settings-mcp-runtime-health-check"
      >
        <Activity size={12} />
        Runtime check
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={onRefresh}
        loading={loading}
        data-testid="settings-mcp-approvals-refresh"
      >
        <RefreshCw size={12} />
        Refresh
      </Button>
    </div>
  </div>
)
