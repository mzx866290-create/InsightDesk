import React from 'react'

import type { SecurityStatusResponse } from '../../api/client'
import { SecurityAuditKpiItem } from './SecurityAuditKpiItem'

export interface SecurityAuditStatusPanelProps {
  securityStatus: SecurityStatusResponse | null
}

export const SecurityAuditStatusPanel: React.FC<SecurityAuditStatusPanelProps> = ({
  securityStatus,
}) => (
  <div
    className="grid gap-2 rounded-lg border border-bg-border bg-bg-primary/30 p-3 text-xs text-text-secondary sm:grid-cols-2 lg:grid-cols-4"
    data-testid="settings-security-status"
  >
    <SecurityAuditKpiItem
      label="Remote sharing"
      value={securityStatus ? (securityStatus.remote_share_ready ? 'Ready' : 'Blocked') : '-'}
      tone={securityStatus && !securityStatus.remote_share_ready ? 'red' : 'default'}
    />
    <SecurityAuditKpiItem
      label="Share secret"
      value={securityStatus ? (securityStatus.share_link_secret_healthy ? 'Healthy' : 'Weak') : '-'}
      tone={securityStatus && !securityStatus.share_link_secret_healthy ? 'red' : 'green'}
    />
    <SecurityAuditKpiItem
      label="Default secret"
      value={securityStatus ? (securityStatus.share_link_secret_uses_default ? 'Yes' : 'No') : '-'}
      tone={securityStatus?.share_link_secret_uses_default ? 'red' : 'default'}
    />
    <SecurityAuditKpiItem
      label="Minimum length"
      value={securityStatus?.share_link_secret_min_length || '-'}
    />
    <SecurityAuditKpiItem
      label="Rate limit"
      value={securityStatus ? (securityStatus.remote_management_rate_limit_enabled ? 'Enabled' : 'Disabled') : '-'}
      tone={securityStatus?.remote_management_rate_limit_enabled ? 'green' : 'default'}
    />
    <SecurityAuditKpiItem
      label="Tracked callers"
      value={securityStatus?.remote_management_rate_limit_tracked_principal_count ?? '-'}
    />
    <SecurityAuditKpiItem
      label="Rate blocks"
      value={securityStatus?.remote_management_rate_limit_blocked_count ?? '-'}
      tone={
        securityStatus && securityStatus.remote_management_rate_limit_blocked_count > 0
          ? 'red'
          : 'default'
      }
    />
    <SecurityAuditKpiItem
      label="Next reset"
      value={
        securityStatus
          ? `${securityStatus.remote_management_rate_limit_next_reset_after_seconds}s`
          : '-'
      }
    />
  </div>
)
