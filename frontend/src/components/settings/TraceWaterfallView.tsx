import React from 'react'
import type { TraceEvent } from '../../api/client'
import {
  TRACE_EVENT_STYLE,
  attributesSummary,
  buildTraceWaterfallGroups,
  clampText,
  formatDuration,
  formatTimestamp,
  shortId,
} from './traceOperationsModel'

interface TraceWaterfallViewProps {
  events: TraceEvent[]
  loading: boolean
}

export const TraceWaterfallView: React.FC<TraceWaterfallViewProps> = ({ events, loading }) => {
  const groups = buildTraceWaterfallGroups(events)

  if (groups.length === 0 && !loading) return null

  return (
    <div className="overflow-hidden rounded-lg border border-bg-border" data-testid="settings-trace-waterfall">
      <div className="flex items-center justify-between border-b border-bg-border bg-bg-tertiary/60 px-3 py-2">
        <div>
          <h4 className="text-sm font-semibold text-text-primary">Trace 瀑布</h4>
          <p className="text-[11px] text-text-secondary">
            按 trace_id 聚合；有 parent_span_id 时嵌套，否则按时间平铺。
          </p>
        </div>
        {loading && <span className="h-4 w-4 animate-spin rounded-full border-2 border-accent-blue border-t-transparent" />}
      </div>

      <div className="space-y-3 p-3">
        {groups.slice(0, 8).map((group) => (
          <section key={group.traceId} className="rounded-md border border-bg-border/70 bg-bg-secondary/40">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-bg-border/70 px-3 py-2 text-xs">
              <div className="min-w-0">
                <p className="truncate font-mono text-[11px] text-text-primary" title={group.traceId}>
                  trace {shortId(group.traceId)}
                </p>
                <p className="text-[10px] text-text-secondary">{formatTimestamp(group.startTimestamp)}</p>
              </div>
              <div className="font-mono text-[11px] text-text-secondary">
                {group.rows.length} spans · {formatDuration(group.durationMs)}
              </div>
            </div>

            <div className="divide-y divide-bg-border/60">
              {group.rows.map((row) => (
                <div
                  key={`${row.traceId}:${row.spanId}`}
                  className="grid gap-2 px-3 py-2 text-xs md:grid-cols-[minmax(10rem,0.9fr)_minmax(14rem,1.4fr)_5rem_6rem] md:items-center"
                  data-testid="settings-trace-waterfall-row"
                >
                  <div className="min-w-0" style={{ paddingLeft: `${Math.min(row.depth, 6) * 14}px` }}>
                    <p className="truncate font-medium text-text-primary" title={row.name}>
                      {row.depth > 0 ? '↳ ' : ''}{row.name}
                    </p>
                    <p className="truncate font-mono text-[10px] text-text-secondary/70">
                      {shortId(row.spanId)}
                      {row.parentSpanId ? ` ← ${shortId(row.parentSpanId)}` : ''}
                    </p>
                  </div>

                  <div className="min-w-0">
                    <div className="relative h-5 overflow-hidden rounded bg-bg-tertiary">
                      <div
                        className={`absolute top-0 h-full rounded ${row.event === 'error' ? 'bg-accent-red/70' : 'bg-accent-blue/70'}`}
                        style={{ left: `${row.offsetPercent}%`, width: `${row.widthPercent}%` }}
                        title={`${row.name} · ${formatDuration(row.durationMs)}`}
                      />
                    </div>
                    <p className={`mt-1 truncate text-[10px] ${row.event === 'error' ? 'text-accent-red' : 'text-text-secondary'}`} title={row.errorText || attributesSummary(row.attributes)}>
                      {row.errorText ? clampText(row.errorText) : attributesSummary(row.attributes)}
                    </p>
                  </div>

                  <span className={`w-fit rounded-full px-2 py-0.5 text-[11px] font-medium ${TRACE_EVENT_STYLE[row.event]}`}>
                    {row.event}
                  </span>
                  <span className="font-mono text-[11px] text-text-primary">{formatDuration(row.durationMs)}</span>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}
