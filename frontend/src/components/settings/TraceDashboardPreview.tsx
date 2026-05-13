import React from 'react'
import { BarChart3, FileJson } from 'lucide-react'
import type { TraceDashboardCard, TraceExportPreview, TracePanelTemplate } from '../../api/client'
import { formatDuration, formatNodeSummary } from './traceOperationsModel'

interface TraceDashboardPreviewProps {
  dashboardCards: TraceDashboardCard[]
  exportPreview: TraceExportPreview | null
  panelTemplates: TracePanelTemplate[]
}

export const TraceDashboardPreview: React.FC<TraceDashboardPreviewProps> = ({
  dashboardCards,
  exportPreview,
  panelTemplates,
}) => {
  if (dashboardCards.length === 0 && !exportPreview) return null

  return (
    <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.8fr)]" data-testid="settings-trace-dashboard-preview">
      <div className="rounded-lg border border-bg-border bg-bg-tertiary/30 p-3">
        <div className="mb-2 flex items-center gap-2 text-xs font-medium text-text-primary">
          <BarChart3 size={13} className="text-accent-blue" />
          Dashboard cards
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          {dashboardCards.map((card) => (
            <div key={card.id} className="rounded border border-bg-border bg-bg-primary/40 px-3 py-2">
              <p className="truncate text-[11px] text-text-secondary">{card.title}</p>
              <p className={card.severity === 'warning' || card.severity === 'error' ? 'mt-1 font-mono text-sm text-accent-red' : 'mt-1 font-mono text-sm text-text-primary'}>
                {card.value}
                {card.unit ? <span className="ml-1 text-[10px] text-text-secondary">{card.unit}</span> : null}
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-bg-border bg-bg-tertiary/30 p-3">
        <div className="mb-2 flex items-center gap-2 text-xs font-medium text-text-primary">
          <FileJson size={13} className="text-accent-green" />
          OTLP export preview
        </div>
        <div className="space-y-1.5 text-xs text-text-secondary">
          <p>service.name：<b className="text-text-primary">{exportPreview?.service_name ?? '-'}</b></p>
          <p>spans/logs：<b className="text-text-primary">{exportPreview?.span_count ?? 0}</b> / {exportPreview?.log_record_count ?? 0}</p>
          <p>sources：<b className="text-text-primary">{formatNodeSummary(exportPreview?.source_nodes)}</b></p>
          <p>processes：<b className="text-text-primary">{formatNodeSummary(exportPreview?.process_nodes)}</b></p>
          <p>avg duration：<b className="text-text-primary">{formatDuration(exportPreview?.avg_duration_ms ?? null)}</b></p>
          {panelTemplates.length > 0 && (
            <p className="truncate" title={panelTemplates.map((template) => template.title).join(' | ')}>
              templates：<b className="text-text-primary">{panelTemplates.map((template) => template.id).join(' | ')}</b>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
