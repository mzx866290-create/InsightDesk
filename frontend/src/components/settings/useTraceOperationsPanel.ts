import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  type TraceDashboardCard,
  type TraceEvent,
  type TraceEventKind,
  type TraceExportPreview,
  type TraceFilters,
  type TracePanelTemplate,
  type TraceSummary,
} from '../../api/client'
import {
  clearTraceEventsState,
  loadTraceEventsState,
} from './traceOperationsActions'
import {
  compactTraceFilters,
  hasTraceFilters,
  latestTraceTimestamp,
  normalizeDashboardCards,
  normalizePanelTemplates,
  normalizeSummary,
  traceActionErrorMessage,
} from './traceOperationsModel'

export function useTraceOperationsPanel() {
  const [limit, setLimit] = useState<number>(100)
  const [eventFilter, setEventFilter] = useState<TraceEventKind | ''>('')
  const [nameFilter, setNameFilter] = useState('')
  const [traceIdFilter, setTraceIdFilter] = useState('')
  const [spanIdFilter, setSpanIdFilter] = useState('')
  const [appliedFilters, setAppliedFilters] = useState<TraceFilters>({})
  const [events, setEvents] = useState<TraceEvent[]>([])
  const [summary, setSummary] = useState<TraceSummary>(() => normalizeSummary(100))
  const [dashboardCards, setDashboardCards] = useState<TraceDashboardCard[]>([])
  const [panelTemplates, setPanelTemplates] = useState<TracePanelTemplate[]>([])
  const [exportPreview, setExportPreview] = useState<TraceExportPreview | null>(null)
  const [loading, setLoading] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const draftFilters = useMemo(
    () =>
      compactTraceFilters({
        event: eventFilter,
        name: nameFilter,
        trace_id: traceIdFilter,
        span_id: spanIdFilter,
      }),
    [eventFilter, nameFilter, spanIdFilter, traceIdFilter],
  )

  const loadTraces = useCallback(async (nextLimit = limit, nextFilters = appliedFilters) => {
    const compactFilters = compactTraceFilters(nextFilters)
    setLoading(true)
    setError(null)
    setNotice(null)
    try {
      const data = await loadTraceEventsState(nextLimit, compactFilters)
      setEvents(data.events)
      setSummary(data.summary ?? normalizeSummary(nextLimit, compactFilters))
      setDashboardCards(normalizeDashboardCards(data.dashboard_cards))
      setPanelTemplates(normalizePanelTemplates(data.panel_templates))
      setExportPreview(data.export_preview ?? null)
    } catch (err) {
      setError(traceActionErrorMessage(err, 'Failed to load traces'))
    } finally {
      setLoading(false)
    }
  }, [appliedFilters, limit])

  useEffect(() => {
    void loadTraces(limit, appliedFilters)
  }, [appliedFilters, limit, loadTraces])

  const handleApplyFilters = useCallback(() => {
    setAppliedFilters(draftFilters)
  }, [draftFilters])

  const handleResetFilters = useCallback(() => {
    setEventFilter('')
    setNameFilter('')
    setTraceIdFilter('')
    setSpanIdFilter('')
    setAppliedFilters({})
  }, [])

  const handleClear = useCallback(async () => {
    setClearing(true)
    setError(null)
    setNotice(null)
    try {
      await clearTraceEventsState()
      setEvents([])
      setSummary(normalizeSummary(limit, appliedFilters))
      setDashboardCards([])
      setPanelTemplates([])
      setExportPreview(null)
      setNotice('Trace cleared')
    } catch (err) {
      setError(traceActionErrorMessage(err, 'Failed to clear traces'))
    } finally {
      setClearing(false)
    }
  }, [appliedFilters, limit])

  const latestTimestamp = useMemo(() => {
    return latestTraceTimestamp(events)
  }, [events])
  const filtersActive = hasTraceFilters(appliedFilters)
  const canResetFilters = filtersActive || hasTraceFilters(draftFilters)

  return {
    appliedFilters,
    canResetFilters,
    clearing,
    dashboardCards,
    draftFilters,
    error,
    eventFilter,
    events,
    exportPreview,
    filtersActive,
    handleApplyFilters,
    handleClear,
    handleResetFilters,
    latestTimestamp,
    limit,
    loadTraces,
    loading,
    nameFilter,
    notice,
    panelTemplates,
    setEventFilter,
    setLimit,
    setNameFilter,
    setSpanIdFilter,
    setTraceIdFilter,
    spanIdFilter,
    summary,
    traceIdFilter,
  }
}
