import React from 'react'
import {
  CheckCircle,
  LockKeyhole,
  ShieldAlert,
  ShieldCheck,
  Trash2,
} from 'lucide-react'
import type { McpConnector } from '../../api/client'
import { Button } from '../ui/Button'
import {
  connectorNeedsApproval,
  hasApproval,
  riskClass,
  sourceLabel,
} from './mcpApprovalsModel'

interface McpApprovalRowProps {
  connector: McpConnector
  approvedConnectors: string[]
  runtimeConnectors: string[]
  envConnectors: string[]
  sources: string[]
  actingName: string | null
  loading: boolean
  onApprove: (name: string) => void
  onRevoke: (name: string) => void
}

export const McpApprovalRow: React.FC<McpApprovalRowProps> = ({
  connector,
  approvedConnectors,
  runtimeConnectors,
  envConnectors,
  sources,
  actingName,
  loading,
  onApprove,
  onRevoke,
}) => {
  const riskLevel = connector.policy?.risk_level ?? connector.risk_level ?? 'medium'
  const approved = hasApproval(connector.name, approvedConnectors)
  const runtimeApproved = hasApproval(connector.name, runtimeConnectors)
  const envApproved = hasApproval(connector.name, envConnectors)
  const needsApproval = connectorNeedsApproval(connector)
  const actionDisabled = actingName !== null || loading

  return (
    <div
      className="grid gap-2 border-t border-bg-border px-3 py-2 text-xs text-text-secondary first:border-t-0 md:grid-cols-[minmax(13rem,1.3fr)_7rem_7rem_minmax(11rem,1fr)_9rem] md:items-center md:gap-3"
      data-testid="settings-mcp-approval-row"
      data-connector-name={connector.name}
    >
      <div className="min-w-0">
        <p className="truncate font-medium text-text-primary">{connector.label || connector.name}</p>
        <p className="mt-0.5 line-clamp-2 text-[11px] leading-relaxed text-text-secondary/80">
          {connector.description || connector.name}
        </p>
      </div>
      <div>
        <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${riskClass(riskLevel)}`}>
          {riskLevel}
        </span>
      </div>
      <div className="flex items-center gap-1.5">
        {approved ? (
          <CheckCircle size={13} className="text-accent-green" />
        ) : needsApproval ? (
          <ShieldAlert size={13} className="text-accent-red" />
        ) : (
          <ShieldCheck size={13} className="text-accent-blue" />
        )}
        <span className={approved ? 'text-accent-green' : needsApproval ? 'text-accent-red' : 'text-text-secondary'}>
          {approved ? 'approved' : needsApproval ? 'pending' : 'not required'}
        </span>
      </div>
      <div className="flex flex-wrap gap-1">
        {sources.length > 0 ? (
          sources.map((source) => (
            <span key={source} className="rounded-full bg-bg-hover px-2 py-0.5 text-[11px] text-text-secondary">
              {sourceLabel(source)}
            </span>
          ))
        ) : (
          <span className="text-[11px] text-text-secondary/70">-</span>
        )}
        {envApproved && !runtimeApproved && (
          <span className="inline-flex items-center gap-1 rounded-full bg-bg-hover px-2 py-0.5 text-[11px] text-text-secondary">
            <LockKeyhole size={10} />
            env
          </span>
        )}
      </div>
      <div>
        {runtimeApproved ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onRevoke(connector.name)}
            loading={actingName === connector.name}
            disabled={actionDisabled && actingName !== connector.name}
            className="text-accent-red hover:text-accent-red"
            data-testid={`settings-mcp-revoke-${connector.name}`}
          >
            <Trash2 size={12} />
            Revoke
          </Button>
        ) : (
          <Button
            variant={needsApproval && !approved ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => onApprove(connector.name)}
            loading={actingName === connector.name}
            disabled={actionDisabled || approved}
            data-testid={`settings-mcp-approve-${connector.name}`}
          >
            <ShieldCheck size={12} />
            Approve
          </Button>
        )}
      </div>
    </div>
  )
}
