import React from 'react'
import { AlertTriangle, RefreshCw, Trash2 } from 'lucide-react'

import { Button } from '../ui/Button'
import { TRACE_LIMIT_OPTIONS } from './traceOperationsModel'

interface TraceOperationsToolbarProps {
  clearing: boolean
  hasEvents: boolean
  limit: number
  loading: boolean
  onClear: () => void
  onLimitChange: (limit: number) => void
  onRefresh: () => void
}

export const TraceOperationsToolbar: React.FC<TraceOperationsToolbarProps> = ({
  clearing,
  hasEvents,
  limit,
  loading,
  onClear,
  onLimitChange,
  onRefresh,
}) => {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h3 className="flex items-center gap-2 text-sm font-medium text-text-primary">
        <AlertTriangle size={14} className="text-accent-blue" />
        Trace 运维
      </h3>
      <div className="flex flex-wrap items-center gap-2">
        <select
          className="input-base py-1 text-xs"
          value={limit}
          onChange={(event) => onLimitChange(Number(event.target.value))}
          data-testid="settings-trace-limit"
        >
          {TRACE_LIMIT_OPTIONS.map((option) => (
            <option key={option} value={option}>
              最近 {option}
            </option>
          ))}
        </select>
        <Button
          variant="ghost"
          size="sm"
          onClick={onRefresh}
          loading={loading}
          data-testid="settings-trace-refresh"
        >
          <RefreshCw size={12} />
          刷新
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClear}
          loading={clearing}
          disabled={!hasEvents}
          className="text-accent-red hover:text-accent-red"
          data-testid="settings-trace-clear"
        >
          <Trash2 size={12} />
          清空
        </Button>
      </div>
    </div>
  )
}
