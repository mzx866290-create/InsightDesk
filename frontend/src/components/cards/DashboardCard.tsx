import React, { useMemo, useState } from 'react'
import { AlertTriangle, BarChart3, ChevronDown, ChevronUp, ShieldCheck } from 'lucide-react'
import { EChartsRenderer, type ChartData } from '../charts/EChartsRenderer'

export interface DashboardMetricItem {
  label: string
  value: string | number
  unit?: string
  trend?: 'up' | 'down' | 'flat'
  delta?: string
  highlight?: boolean
  evidence_ids?: string[]
}

export interface DashboardChartItem {
  title: string
  type: 'bar' | 'line' | 'pie'
  description?: string
  evidence_ids?: string[]
  chart_data: ChartData
}

export interface DashboardTableData {
  title?: string
  columns: string[]
  rows: Record<string, string | number>[]
  evidence_ids?: string[]
}

export interface DashboardEvidenceItem {
  id: string
  title: string
  snippet: string
  source_type?: string
}

export interface DashboardCardData {
  title?: string
  summary?: string
  metrics?: DashboardMetricItem[]
  charts?: DashboardChartItem[]
  table?: DashboardTableData | null
  evidence?: DashboardEvidenceItem[]
  warnings?: string[]
}

interface DashboardCardProps {
  data: DashboardCardData
  streaming?: boolean
}

function evidenceLookup(evidence: DashboardEvidenceItem[] | undefined) {
  const map = new Map<string, DashboardEvidenceItem>()
  for (const item of evidence ?? []) {
    if (item.id) map.set(item.id, item)
  }
  return map
}

function evidenceTitles(refs: string[] | undefined, evidenceMap: Map<string, DashboardEvidenceItem>) {
  return (refs ?? [])
    .map((ref) => evidenceMap.get(ref)?.title)
    .filter((value): value is string => Boolean(value))
}

export const DashboardCard: React.FC<DashboardCardProps> = ({ data, streaming }) => {
  const [showTable, setShowTable] = useState(false)
  const [activeChartIndex, setActiveChartIndex] = useState(0)
  const [showEvidence, setShowEvidence] = useState(false)

  const metrics = data.metrics ?? []
  const charts = (data.charts ?? []).filter((chart) =>
    chart?.chart_data?.type === 'bar' || chart?.chart_data?.type === 'line' || chart?.chart_data?.type === 'pie',
  )
  const warnings = data.warnings ?? []
  const evidence = data.evidence ?? []
  const table = data.table
  const evidenceMap = useMemo(() => evidenceLookup(evidence), [evidence])
  const activeChart = charts[activeChartIndex] ?? charts[0]

  return (
    <div className="my-3 overflow-hidden rounded-xl border border-accent-blue/25 bg-bg-secondary/60 shadow-sm">
      <div className="border-b border-accent-blue/15 bg-accent-blue/8 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-blue/20">
            <BarChart3 size={18} className="text-accent-blue" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-sm font-semibold text-text-primary">
              {data.title ?? '知识库仪表盘'}
              {streaming && <span className="ml-1 animate-pulse text-text-secondary">…</span>}
            </h3>
            {data.summary && (
              <p className="mt-1 text-xs leading-relaxed text-text-secondary/80">{data.summary}</p>
            )}
          </div>
        </div>
      </div>

      {metrics.length > 0 && (
        <div className="grid grid-cols-2 gap-2 px-4 py-4 sm:grid-cols-3">
          {metrics.map((metric, index) => (
            <div
              key={`${metric.label}-${index}`}
              className={`rounded-lg border px-3 py-2.5 ${
                metric.highlight
                  ? 'border-accent-blue/30 bg-accent-blue/10'
                  : 'border-bg-border bg-bg-tertiary/40'
              }`}
            >
              <p className="truncate text-[10px] uppercase tracking-wider text-text-secondary/60">
                {metric.label}
              </p>
              <div className="mt-1 flex items-end gap-1">
                <span className="text-lg font-bold leading-tight text-text-primary">{metric.value}</span>
                {metric.unit && (
                  <span className="pb-0.5 text-[11px] text-text-secondary/60">{metric.unit}</span>
                )}
              </div>
              {(metric.delta || metric.trend) && (
                <p className="mt-1 text-[10px] text-text-secondary/70">
                  {metric.trend === 'up' ? '上升' : metric.trend === 'down' ? '下降' : '持平'}
                  {metric.delta ? ` · ${metric.delta}` : ''}
                </p>
              )}
              {metric.evidence_ids && metric.evidence_ids.length > 0 && (
                <p className="mt-1 line-clamp-2 text-[10px] text-text-secondary/60">
                  证据: {evidenceTitles(metric.evidence_ids, evidenceMap).join(' / ')}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {charts.length > 0 && activeChart && (
        <div className="border-t border-bg-border px-4 py-4">
          <div className="mb-3 flex flex-wrap gap-2">
            {charts.map((chart, index) => (
              <button
                key={`${chart.title}-${index}`}
                onClick={() => setActiveChartIndex(index)}
                className={`rounded-md border px-2.5 py-1 text-[11px] transition-colors ${
                  index === activeChartIndex
                    ? 'border-accent-blue/50 bg-accent-blue/15 text-accent-blue'
                    : 'border-bg-border text-text-secondary hover:text-text-primary'
                }`}
              >
                {chart.title}
              </button>
            ))}
          </div>
          <div className="rounded-xl border border-bg-border bg-bg-primary/40 p-3">
            <div className="mb-2">
              <p className="text-xs font-medium text-text-primary">{activeChart.title}</p>
              {activeChart.description && (
                <p className="mt-1 text-[11px] leading-relaxed text-text-secondary/75">{activeChart.description}</p>
              )}
            </div>
            <EChartsRenderer chartData={activeChart.chart_data} height={280} />
            {activeChart.evidence_ids && activeChart.evidence_ids.length > 0 && (
              <p className="mt-2 text-[11px] text-text-secondary/70">
                图表证据: {evidenceTitles(activeChart.evidence_ids, evidenceMap).join(' / ')}
              </p>
            )}
          </div>
        </div>
      )}

      {table && table.columns.length > 0 && table.rows.length > 0 && (
        <div className="border-t border-bg-border px-4 py-4">
          <button
            onClick={() => setShowTable((value) => !value)}
            className="flex items-center gap-1 text-[11px] text-accent-blue/80 transition-colors hover:text-accent-blue"
          >
            {showTable ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
            {showTable ? '收起数据明细' : `展开数据明细${table.title ? ` · ${table.title}` : ''}`}
          </button>
          {showTable && (
            <div className="mt-3 overflow-x-auto rounded-lg border border-bg-border text-xs">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-bg-tertiary/60">
                    {table.columns.map((column) => (
                      <th
                        key={column}
                        className="border-b border-bg-border px-3 py-1.5 text-left text-[10px] font-semibold uppercase tracking-wider text-text-secondary/70"
                      >
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {table.rows.map((row, rowIndex) => (
                    <tr key={rowIndex} className="border-b border-bg-border/50 last:border-b-0">
                      {table.columns.map((column) => (
                        <td key={`${rowIndex}-${column}`} className="px-3 py-1.5 text-text-primary/85">
                          {String(row[column] ?? '')}
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

      {warnings.length > 0 && (
        <div className="border-t border-bg-border px-4 py-3">
          <div className="rounded-lg border border-amber-400/25 bg-amber-400/10 px-3 py-2 text-xs text-amber-300">
            <div className="mb-1 flex items-center gap-1.5 font-medium">
              <AlertTriangle size={12} />
              口径提示
            </div>
            <ul className="space-y-1">
              {warnings.map((warning, index) => (
                <li key={`${warning}-${index}`}>{warning}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {evidence.length > 0 && (
        <div className="border-t border-bg-border px-4 py-4">
          <button
            onClick={() => setShowEvidence((value) => !value)}
            className="flex items-center gap-1 text-[11px] text-accent-blue/80 transition-colors hover:text-accent-blue"
          >
            {showEvidence ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
            查看证据来源 ({evidence.length})
          </button>
          {showEvidence && (
            <div className="mt-3 space-y-2">
              {evidence.map((item) => (
                <div key={item.id} className="rounded-lg border border-bg-border bg-bg-tertiary/35 p-3">
                  <div className="flex items-center gap-1.5 text-[11px] font-medium text-text-primary">
                    <ShieldCheck size={11} className="text-accent-green" />
                    {item.id} · {item.title}
                  </div>
                  <p className="mt-1 text-[11px] leading-relaxed text-text-secondary/75">{item.snippet}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
