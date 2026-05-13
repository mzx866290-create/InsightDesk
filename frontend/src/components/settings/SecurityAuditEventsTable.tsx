import React from 'react'

import type { SecurityAuditEvent } from '../../api/client'
import {
  clampText,
  formatDetails,
  formatTimestamp,
  resultBadgeClass,
} from './securityAuditSummaryModel'

export interface SecurityAuditEventsTableProps {
  events: SecurityAuditEvent[]
  loading: boolean
}

export const SecurityAuditEventsTable: React.FC<SecurityAuditEventsTableProps> = ({
  events,
  loading,
}) => {
  return (
    <>
      <div className="hidden grid-cols-[minmax(11rem,1.2fr)_minmax(12rem,1.2fr)_6rem_minmax(11rem,1fr)_minmax(14rem,1.4fr)] gap-3 bg-bg-tertiary/40 px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-text-secondary md:grid">
        <span>Time</span>
        <span>Action</span>
        <span>Result</span>
        <span>Actor</span>
        <span>Details</span>
      </div>

      {loading && events.length === 0 && (
        <div className="flex justify-center py-8">
          <span className="h-5 w-5 animate-spin rounded-full border-2 border-accent-blue border-t-transparent" />
        </div>
      )}

      {!loading && events.length === 0 && (
        <div className="px-3 py-8 text-center text-xs text-text-secondary" data-testid="settings-security-audit-empty">
          No audit events.
        </div>
      )}

      {events.map((event, index) => {
        const details = clampText(formatDetails(event.details))
        const actor = [event.user_role, event.user_id].filter(Boolean).join(': ') || '-'
        const requestMeta = [event.request_id, event.ip].filter(Boolean).join(' | ')
        return (
          <div
            key={`${event.request_id}:${event.action}:${event.timestamp}:${index}`}
            className="grid gap-2 border-t border-bg-border px-3 py-2 text-xs text-text-secondary first:border-t-0 md:grid-cols-[minmax(11rem,1.2fr)_minmax(12rem,1.2fr)_6rem_minmax(11rem,1fr)_minmax(14rem,1.4fr)] md:gap-3"
            data-testid="settings-security-audit-event-row"
          >
            <div className="min-w-0">
              <p className="truncate text-text-primary">{formatTimestamp(event.timestamp)}</p>
              <p className="mt-0.5 truncate font-mono text-[10px] text-text-secondary/70" title={requestMeta}>
                {requestMeta || '-'}
              </p>
            </div>
            <div className="min-w-0">
              <p className="truncate font-mono text-[11px] text-text-primary" title={event.action || '-'}>
                {event.action || '-'}
              </p>
              <p className="mt-0.5 truncate text-[10px] text-text-secondary/70">
                {event.auth_mode || '-'} / {event.auth_source || '-'}{event.is_local ? ' / local' : ''}
              </p>
            </div>
            <div>
              <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${resultBadgeClass(event.result)}`}>
                {event.result || '-'}
              </span>
            </div>
            <div className="min-w-0 truncate" title={actor}>
              {actor}
            </div>
            <div className="min-w-0 truncate font-mono text-[11px]" title={formatDetails(event.details)}>
              {details}
            </div>
          </div>
        )
      })}
    </>
  )
}
