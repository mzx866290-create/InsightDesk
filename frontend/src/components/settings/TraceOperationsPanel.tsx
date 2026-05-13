import React from 'react'

import { TraceDashboardPreview } from './TraceDashboardPreview'
import { TraceEventList } from './TraceEventList'
import { TraceOperationsFilters } from './TraceOperationsFilters'
import { TraceOperationsMessage } from './TraceOperationsMessage'
import { TraceOperationsSummary } from './TraceOperationsSummary'
import { TraceOperationsToolbar } from './TraceOperationsToolbar'
import { TraceWaterfallView } from './TraceWaterfallView'
import { useTraceOperationsPanel } from './useTraceOperationsPanel'

export const TraceOperationsPanel: React.FC = () => {
  const controller = useTraceOperationsPanel()

  return (
    <div className="space-y-4" data-testid="settings-trace-panel">
      <TraceOperationsToolbar
        clearing={controller.clearing}
        hasEvents={controller.events.length > 0}
        limit={controller.limit}
        loading={controller.loading}
        onClear={() => void controller.handleClear()}
        onLimitChange={controller.setLimit}
        onRefresh={() => void controller.loadTraces()}
      />

      <TraceOperationsFilters
        eventFilter={controller.eventFilter}
        nameFilter={controller.nameFilter}
        traceIdFilter={controller.traceIdFilter}
        spanIdFilter={controller.spanIdFilter}
        loading={controller.loading}
        canResetFilters={controller.canResetFilters}
        onEventFilterChange={controller.setEventFilter}
        onNameFilterChange={controller.setNameFilter}
        onTraceIdFilterChange={controller.setTraceIdFilter}
        onSpanIdFilterChange={controller.setSpanIdFilter}
        onApplyFilters={controller.handleApplyFilters}
        onResetFilters={controller.handleResetFilters}
      />

      <TraceOperationsSummary
        filtersActive={controller.filtersActive}
        latestTimestamp={controller.latestTimestamp}
        summary={controller.summary}
      />

      <TraceDashboardPreview
        dashboardCards={controller.dashboardCards}
        exportPreview={controller.exportPreview}
        panelTemplates={controller.panelTemplates}
      />

      <TraceOperationsMessage error={controller.error} notice={controller.notice} />

      <TraceWaterfallView events={controller.events} loading={controller.loading} />

      <TraceEventList events={controller.events} loading={controller.loading} />
    </div>
  )
}
