import React from 'react'
import { History, RefreshCw } from 'lucide-react'

import type { IntegratorAuditEvent } from '../../api/client'
import { formatAuditTime, safeAuditDetails } from './integratorAuditModel'
import { Button } from '../ui/Button'

export interface IntegratorAuditPanelProps {
  auditEvents: IntegratorAuditEvent[]
  auditError: string | null
  auditLoading: boolean
  onRefreshAudit: () => void | Promise<void>
}

export const IntegratorAuditPanel: React.FC<IntegratorAuditPanelProps> = ({
  auditEvents,
  auditError,
  auditLoading,
  onRefreshAudit,
}) => {
  return (
    <div
      className="rounded-lg border border-bg-border bg-bg-tertiary/20 p-3"
      data-testid="settings-integrator-audit-panel"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h4 className="flex items-center gap-2 text-sm font-medium text-text-primary">
            <History size={14} className="text-accent-blue" />
            Recent audit
          </h4>
          <p className="mt-1 text-xs text-text-secondary">Redacted connector activity from the audit log.</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void onRefreshAudit()}
          loading={auditLoading}
          data-testid="settings-integrator-audit-refresh"
        >
          <RefreshCw size={12} />
          Refresh audit
        </Button>
      </div>

      {auditError && (
        <div
          className="mt-3 rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red"
          data-testid="settings-integrator-audit-error"
        >
          {auditError}
        </div>
      )}

      {!auditError && auditEvents.length === 0 && !auditLoading && (
        <div
          className="mt-3 rounded-lg border border-dashed border-bg-border px-3 py-6 text-center text-xs text-text-secondary"
          data-testid="settings-integrator-audit-empty"
        >
          No audit records yet.
        </div>
      )}

      {!auditError && auditEvents.length > 0 && (
        <div className="mt-3 space-y-2" data-testid="settings-integrator-audit-list">
          {auditEvents.map((event, index) => {
            const details = safeAuditDetails(event.details)

            return (
              <div
                key={`${event.request_id || event.action}-${event.timestamp}-${index}`}
                className="rounded-lg border border-bg-border bg-bg-secondary/40 px-3 py-2"
                data-testid="settings-integrator-audit-row"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-medium text-text-primary">{event.action || 'integration_event'}</span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[11px] ${
                          event.result === 'success' || event.result === 'allowed'
                            ? 'bg-accent-green/15 text-accent-green'
                            : event.result === 'failed' || event.result === 'denied'
                              ? 'bg-accent-red/15 text-accent-red'
                              : 'bg-bg-hover text-text-secondary'
                        }`}
                      >
                        {event.result || 'unknown'}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-text-secondary">
                      <span>{formatAuditTime(event.timestamp)}</span>
                      {event.connector_id && <span>connector: {event.connector_id}</span>}
                      {event.connector_type && <span>type: {event.connector_type}</span>}
                      {event.actor && <span>actor: {event.actor}</span>}
                    </div>
                  </div>
                  {event.request_id && (
                    <span className="shrink-0 text-[11px] text-text-secondary">{event.request_id}</span>
                  )}
                </div>
                {details.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {details.map(([key, value]) => (
                      <span
                        key={key}
                        className="rounded-md bg-bg-hover px-2 py-1 text-[11px] text-text-secondary"
                      >
                        {key}: {value}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
