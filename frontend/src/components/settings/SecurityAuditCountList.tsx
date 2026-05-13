import React, { useMemo } from 'react'
import { BarChart3, Layers3 } from 'lucide-react'

import {
  barClass,
  formatCountName,
  sortedCountEntries,
  valueClass,
  type CountKind,
} from './securityAuditSummaryModel'

export interface SecurityAuditCountListProps {
  title: string
  counts: Record<string, number>
  kind: CountKind
  emptyText: string
  mono?: boolean
  testId: string
  selectedName?: string
  onSelectName?: (name: string) => void
}

export const SecurityAuditCountList: React.FC<SecurityAuditCountListProps> = ({
  title,
  counts,
  kind,
  emptyText,
  mono = false,
  testId,
  selectedName = '',
  onSelectName,
}) => {
  const entries = useMemo(() => sortedCountEntries(counts), [counts])
  const maxCount = entries[0]?.[1] ?? 0

  return (
    <div className="overflow-hidden rounded-lg border border-bg-border" data-testid={testId}>
      <div className="flex items-center gap-2 bg-bg-tertiary/60 px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-text-secondary">
        {kind === 'category' ? <Layers3 size={12} /> : <BarChart3 size={12} />}
        <span>{title}</span>
      </div>

      {entries.length === 0 ? (
        <div className="px-3 py-6 text-center text-xs text-text-secondary">{emptyText}</div>
      ) : (
        <div className="max-h-56 overflow-auto">
          {entries.map(([name, count]) => {
            const width = maxCount > 0 ? Math.max(4, Math.round((count / maxCount) * 100)) : 0
            const label = formatCountName(name)
            return (
              <button
                key={name}
                type="button"
                className={`block w-full border-t border-bg-border px-3 py-2 text-left first:border-t-0 ${
                  onSelectName ? 'hover:bg-bg-hover/50' : ''
                } ${selectedName === name ? 'bg-accent-blue/10' : ''}`}
                onClick={() => onSelectName?.(name)}
                data-testid={`${testId}-row`}
              >
                <div className="flex min-w-0 items-center justify-between gap-3 text-xs">
                  <span
                    className={`min-w-0 truncate text-text-primary ${mono ? 'font-mono text-[11px]' : ''}`}
                    title={label}
                  >
                    {label}
                  </span>
                  <span className={`shrink-0 font-semibold ${valueClass(kind, name)}`}>{count}</span>
                </div>
                <div className="mt-2 h-1.5 rounded-full bg-bg-hover">
                  <div
                    className={`h-1.5 rounded-full ${barClass(kind, name)}`}
                    style={{ width: `${width}%` }}
                  />
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
