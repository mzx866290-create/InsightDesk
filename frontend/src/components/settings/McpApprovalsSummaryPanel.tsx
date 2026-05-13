import React from 'react'

import type { McpConnectorApprovalsResponse } from '../../api/client'

interface McpApprovalsSummaryPanelProps {
  approvals: McpConnectorApprovalsResponse
}

export const McpApprovalsSummaryPanel: React.FC<McpApprovalsSummaryPanelProps> = ({ approvals }) => (
  <div
    className="grid gap-2 rounded-lg border border-bg-border bg-bg-tertiary/30 px-3 py-2 text-xs text-text-secondary sm:grid-cols-4"
    data-testid="settings-mcp-approvals-summary"
  >
    <span data-testid="settings-mcp-approvals-summary-effective">
      Effective: <b className="text-text-primary">{approvals.approved_connectors.length}</b>
    </span>
    <span data-testid="settings-mcp-approvals-summary-runtime">
      Runtime: <b className="text-text-primary">{approvals.runtime_connectors.length}</b>
    </span>
    <span data-testid="settings-mcp-approvals-summary-env">
      Env: <b className="text-text-primary">{approvals.env_connectors.length}</b>
    </span>
    <span data-testid="settings-mcp-approvals-summary-store">
      Store:{' '}
      <b className="text-text-primary">
        {approvals.persistence.enabled ? approvals.persistence.config_key : '-'}
      </b>
    </span>
  </div>
)
