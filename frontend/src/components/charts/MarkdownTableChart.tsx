import React, { useState, useMemo } from 'react'
import { PieChart, AlignLeft } from 'lucide-react'
import { EChartsRenderer, type ChartData } from './EChartsRenderer'

interface MarkdownTableChartProps {
  children: React.ReactNode
  rawHeaders: string[]
  rawRows: (string | number)[][]
}

function isNumeric(v: string | number): boolean {
  if (typeof v === 'number') return !isNaN(v)
  return v.trim() !== '' && !isNaN(Number(v.replace(/[,%¥$€]/g, '')))
}

function toNum(v: string | number): number {
  if (typeof v === 'number') return v
  return Number(v.replace(/[,%¥$€]/g, ''))
}

export const MarkdownTableChart: React.FC<MarkdownTableChartProps> = ({
  children,
  rawHeaders,
  rawRows,
}) => {
  const [viewMode, setViewMode] = useState<'table' | 'chart'>('table')
  const [chartType, setChartType] = useState<'bar' | 'pie' | 'line'>('bar')

  const chartData = useMemo<ChartData | null>(() => {
    if (rawHeaders.length < 2 || rawRows.length === 0) return null
    const numericCols = rawHeaders.slice(1).filter((_, ci) =>
      rawRows.every((row) => isNumeric(row[ci + 1]))
    )
    if (numericCols.length === 0) return null
    return {
      type: chartType,
      labels: rawRows.map((r) => String(r[0] ?? '')),
      datasets: numericCols.map((col, ci) => ({
        label: col,
        data: rawRows.map((row) => toNum(row[ci + 1])),
      })),
    }
  }, [rawHeaders, rawRows, chartType])

  if (!chartData) return <>{children}</>

  return (
    <div className="my-3 rounded-xl border border-bg-border overflow-hidden">
      {/* Toggle bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-bg-tertiary/60 border-b border-bg-border">
        <span className="text-[11px] text-text-secondary/60">数据表格</span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setViewMode('table')}
            className={`p-1 rounded text-[11px] flex items-center gap-1 transition-colors ${
              viewMode === 'table'
                ? 'bg-accent-blue/20 text-accent-blue'
                : 'text-text-secondary hover:text-text-primary'
            }`}
            title="表格视图"
          >
            <AlignLeft size={11} />
            表格
          </button>
          <button
            onClick={() => setViewMode('chart')}
            className={`p-1 rounded text-[11px] flex items-center gap-1 transition-colors ${
              viewMode === 'chart'
                ? 'bg-accent-blue/20 text-accent-blue'
                : 'text-text-secondary hover:text-text-primary'
            }`}
            title="图表视图"
          >
            <PieChart size={11} />
            图表
          </button>
        </div>
      </div>

      {viewMode === 'table' && <div className="overflow-x-auto">{children}</div>}

      {viewMode === 'chart' && chartData && (
        <div className="px-3 py-2">
          <div className="flex gap-1 mb-2">
            {(['bar', 'line', 'pie'] as const).map((type) => (
              <button
                key={type}
                onClick={() => setChartType(type)}
                className={`px-2 py-0.5 text-[11px] rounded border transition-colors ${
                  chartType === type
                    ? 'border-accent-blue/50 bg-accent-blue/15 text-accent-blue'
                    : 'border-bg-border text-text-secondary hover:text-text-primary'
                }`}
              >
                {type === 'bar' ? '柱状图' : type === 'line' ? '折线图' : '饼图'}
              </button>
            ))}
          </div>
          <EChartsRenderer chartData={{ ...chartData, type: chartType }} height={240} />
        </div>
      )}
    </div>
  )
}
