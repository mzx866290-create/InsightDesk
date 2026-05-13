import React from 'react'
import { Trash2 } from 'lucide-react'

import { Button } from '../ui/Button'

export interface McpUnknownApprovalsPanelProps {
  connectorNames: string[]
  actingName: string | null
  onRevoke: (name: string) => void
}

export const McpUnknownApprovalsPanel: React.FC<McpUnknownApprovalsPanelProps> = ({
  connectorNames,
  actingName,
  onRevoke,
}) => {
  if (connectorNames.length === 0) {
    return null
  }

  return (
    <div className="rounded-lg border border-bg-border bg-bg-tertiary/30 px-3 py-2 text-xs text-text-secondary">
      <p className="mb-2 font-medium text-text-primary">Runtime approvals outside the current catalog</p>
      <div className="flex flex-wrap gap-2">
        {connectorNames.map((name) => (
          <Button
            key={name}
            variant="ghost"
            size="sm"
            onClick={() => onRevoke(name)}
            loading={actingName === name}
            className="text-accent-red hover:text-accent-red"
            data-testid={`settings-mcp-revoke-${name}`}
          >
            <Trash2 size={12} />
            {name}
          </Button>
        ))}
      </div>
    </div>
  )
}
