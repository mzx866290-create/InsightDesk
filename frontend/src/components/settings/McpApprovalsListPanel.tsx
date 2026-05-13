import React from 'react'

import type {
  McpConnector,
  McpConnectorApprovalsResponse,
} from '../../api/client'
import { McpApprovalRow } from './McpApprovalRow'

export interface McpApprovalsListPanelProps {
  connectors: McpConnector[]
  approvals: McpConnectorApprovalsResponse
  actingName: string | null
  loading: boolean
  onApprove: (name: string) => void
  onRevoke: (name: string) => void
}

export const McpApprovalsListPanel: React.FC<McpApprovalsListPanelProps> = ({
  connectors,
  approvals,
  actingName,
  loading,
  onApprove,
  onRevoke,
}) => (
  <div className="overflow-hidden rounded-lg border border-bg-border" data-testid="settings-mcp-approvals-list">
    <div className="hidden grid-cols-[minmax(13rem,1.3fr)_7rem_7rem_minmax(11rem,1fr)_9rem] gap-3 bg-bg-tertiary/60 px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-text-secondary md:grid">
      <span>Connector</span>
      <span>Risk</span>
      <span>Approval</span>
      <span>Sources</span>
      <span>Action</span>
    </div>

    {loading && connectors.length === 0 && (
      <div className="flex justify-center py-8">
        <span className="h-5 w-5 animate-spin rounded-full border-2 border-accent-blue border-t-transparent" />
      </div>
    )}

    {!loading && connectors.length === 0 && (
      <div className="px-3 py-8 text-center text-xs text-text-secondary" data-testid="settings-mcp-approvals-empty">
        No MCP connectors.
      </div>
    )}

    {connectors.map((connector) => (
      <McpApprovalRow
        key={connector.name}
        connector={connector}
        approvedConnectors={approvals.approved_connectors}
        runtimeConnectors={approvals.runtime_connectors}
        envConnectors={approvals.env_connectors}
        sources={approvals.sources[connector.name] ?? []}
        actingName={actingName}
        loading={loading}
        onApprove={onApprove}
        onRevoke={onRevoke}
      />
    ))}
  </div>
)
