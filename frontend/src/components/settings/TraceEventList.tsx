import React from 'react'
import type { TraceEvent } from '../../api/client'
import {
  TRACE_EVENT_STYLE,
  attributesSummary,
  clampText,
  formatDuration,
  formatTimestamp,
  shortId,
} from './traceOperationsModel'

interface TraceEventListProps {
  events: TraceEvent[]
  loading: boolean
}

export const TraceEventList: React.FC<TraceEventListProps> = ({ events, loading }) => {
  return (
    <div className="overflow-hidden rounded-lg border border-bg-border" data-testid="settings-trace-event-list">
      <div className="hidden grid-cols-[minmax(10rem,1.25fr)_5rem_6rem_minmax(9rem,1fr)_minmax(12rem,1.4fr)] gap-3 bg-bg-tertiary/60 px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-text-secondary md:grid">
        <span>Name</span>
        <span>Event</span>
        <span>Duration</span>
        <span>Error</span>
        <span>Attributes</span>
      </div>

      {loading && events.length === 0 && (
        <div className="flex justify-center py-8">
          <span className="h-5 w-5 animate-spin rounded-full border-2 border-accent-blue border-t-transparent" />
        </div>
      )}

      {!loading && events.length === 0 && (
        <div className="px-3 py-8 text-center text-xs text-text-secondary" data-testid="settings-trace-empty">
          暂无 Trace。
        </div>
      )}

      {events.map((event) => {
        const errorText = [event.error_type, event.error_message].filter(Boolean).join(': ') || '-'
        return (
          <div
            key={`${event.trace_id}:${event.span_id}:${event.event}:${event.timestamp}`}
            className="grid gap-2 border-t border-bg-border px-3 py-2 text-xs text-text-secondary first:border-t-0 md:grid-cols-[minmax(10rem,1.25fr)_5rem_6rem_minmax(9rem,1fr)_minmax(12rem,1.4fr)] md:gap-3"
            data-testid="settings-trace-event-row"
          >
            <div className="min-w-0">
              <p className="truncate font-medium text-text-primary">{event.name || 'span'}</p>
              <p className="mt-0.5 truncate font-mono text-[10px] text-text-secondary/70">
                {shortId(event.trace_id)} / {shortId(event.span_id)} | {formatTimestamp(event.timestamp)}
              </p>
            </div>
            <div>
              <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${TRACE_EVENT_STYLE[event.event]}`}>
                {event.event}
              </span>
            </div>
            <div className="font-mono text-[11px] text-text-primary">{formatDuration(event.duration_ms)}</div>
            <div className={`min-w-0 truncate ${event.event === 'error' ? 'text-accent-red' : ''}`} title={errorText}>
              {clampText(errorText)}
            </div>
            <div className="min-w-0 truncate text-[11px]" title={attributesSummary(event.attributes)}>
              {attributesSummary(event.attributes)}
            </div>
          </div>
        )
      })}
    </div>
  )
}
