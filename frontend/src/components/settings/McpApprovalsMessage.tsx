import React from 'react'

export interface McpApprovalsMessageProps {
  error: string | null
  notice: string | null
}

export const McpApprovalsMessage: React.FC<McpApprovalsMessageProps> = ({
  error,
  notice,
}) => {
  if (!error && !notice) {
    return null
  }

  return (
    <div
      className={`rounded-lg border px-3 py-2 text-xs ${
        error
          ? 'border-accent-red/30 bg-accent-red/10 text-accent-red'
          : 'border-accent-green/30 bg-accent-green/10 text-accent-green'
      }`}
      data-testid="settings-mcp-approvals-message"
    >
      {error ?? notice}
    </div>
  )
}
