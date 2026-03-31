import React, { useState } from 'react'
import { BarChart2, TrendingUp, TrendingDown, Minus, ChevronDown, ChevronUp } from 'lucide-react'

export interface MetricItem {
  label: string
  value: string | number
  unit?: string
  trend?: 'up' | 'down' | 'flat'
  delta?: string
  highlight?: boolean
}

export interface DataSummaryCardData {
  title?: string
  description?: string
  metrics?: MetricItem[]
  rows?: Record<string, string | number>[]
  columns?: string[]
  note?: string
}

interface DataSummaryCardProps {
  data: DataSummaryCardData
  streaming?: boolean
}

const TrendIcon: React.FC<{ trend?: 'up' | 'down' | 'flat' }> = ({ trend }) => {
  if (trend === 'up') return <TrendingUp size={11} className="text-accent-green" />
  if (trend === 'down') return <TrendingDown size={11} className="text-red-400" />
  return <Minus size={11} className="text-text-secondary/50" />
}

export const DataSummaryCard: React.FC<DataSummaryCardProps> = ({ data, streaming }) => {
  const [showTable, setShowTable] = useState(false)

  return (
    <div className="my-3 rounded-xl border border-accent-blue/25 bg-bg-secondary/60 overflow-hidden shadow-sm">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 bg-accent-blue/8 border-b border-accent-blue/15">
        <div className="p-1.5 rounded-md bg-accent-blue/20">
          <BarChart2 size={14} className="text-accent-blue" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-text-primary">
            {data.title ?? '数据汇总'}
            {streaming && <span className="ml-1 animate-pulse text-text-secondary">…</span>}
          </h3>
          {data.description && (
            <p className="text-xs text-text-secondary/70 mt-0.5 truncate">{data.description}</p>
          )}
        </div>
      </div>

      {/* Metrics grid */}
      {data.metrics && data.metrics.length > 0 && (
        <div className="px-4 py-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {data.metrics.map((m, i) => (
              <div
                key={i}
                className={`rounded-lg px-3 py-2.5 border ${
                  m.highlight
                    ? 'border-accent-blue/30 bg-accent-blue/10'
                    : 'border-bg-border bg-bg-tertiary/40'
                }`}
              >
                <p className="text-[10px] text-text-secondary/60 uppercase tracking-wider truncate">
                  {m.label}
                </p>
                <div className="flex items-end gap-1 mt-1">
                  <span
                    className={`text-lg font-bold leading-tight ${
                      m.highlight ? 'text-accent-blue' : 'text-text-primary'
                    }`}
                  >
                    {m.value}
                  </span>
                  {m.unit && (
                    <span className="text-[11px] text-text-secondary/60 pb-0.5">{m.unit}</span>
                  )}
                </div>
                {(m.trend || m.delta) && (
                  <div className="flex items-center gap-1 mt-1">
                    <TrendIcon trend={m.trend} />
                    {m.delta && (
                      <span
                        className={`text-[10px] ${
                          m.trend === 'up'
                            ? 'text-accent-green'
                            : m.trend === 'down'
                            ? 'text-red-400'
                            : 'text-text-secondary/50'
                        }`}
                      >
                        {m.delta}
                      </span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Optional table */}
      {data.rows && data.rows.length > 0 && data.columns && (
        <div className="px-4 pb-3">
          <button
            onClick={() => setShowTable((v) => !v)}
            className="flex items-center gap-1 text-[11px] text-accent-blue/70 hover:text-accent-blue transition-colors mb-2"
          >
            {showTable ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
            {showTable ? '收起明细表' : '展开明细表'}
          </button>
          {showTable && (
            <div className="overflow-x-auto rounded-lg border border-bg-border text-xs">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-bg-tertiary/60">
                    {data.columns.map((col, i) => (
                      <th
                        key={i}
                        className="px-3 py-1.5 text-left text-[10px] uppercase tracking-wider text-text-secondary/70 font-semibold border-b border-bg-border"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((row, ri) => (
                    <tr
                      key={ri}
                      className="border-b border-bg-border/50 hover:bg-bg-hover/20 transition-colors last:border-0"
                    >
                      {data.columns!.map((col, ci) => (
                        <td key={ci} className="px-3 py-1.5 text-text-primary/80">
                          {String(row[col] ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Note */}
      {data.note && (
        <div className="px-4 pb-3">
          <p className="text-[10px] text-text-secondary/50 italic">{data.note}</p>
        </div>
      )}
    </div>
  )
}
