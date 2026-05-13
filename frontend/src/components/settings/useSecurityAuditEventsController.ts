import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  type SecurityAuditCleanupResponse,
  type SecurityAuditEvent,
  type SecurityAuditEventFilters,
} from '../../api/client'
import type { SecurityAuditEventsPanelProps } from './SecurityAuditEventsPanel'
import {
  buildRetentionPreview,
  hasAuditEventFilters,
  parseRetentionKeepLatest,
} from './securityAuditSummaryModel'
import {
  buildDraftAuditEventFilters,
  cleanupSecurityAuditEventsState,
  createSecurityAuditEventsPanelProps,
  loadSecurityAuditEventsState,
  normalizeAuditEventsCleanupError,
  normalizeAuditEventsLoadError,
  type LoadedSecurityAuditEventsState,
} from './securityAuditEventsControllerModel'

interface UseSecurityAuditEventsControllerOptions {
  limit: number
  onSummaryRefresh: () => Promise<void>
  resultOptions: string[]
}

export interface SecurityAuditEventsController {
  eventsPanelProps: SecurityAuditEventsPanelProps
  selectedAction?: string
  onSelectAction: (action: string) => void
}

export function useSecurityAuditEventsController({
  limit,
  onSummaryRefresh,
  resultOptions,
}: UseSecurityAuditEventsControllerOptions): SecurityAuditEventsController {
  const [actionFilter, setActionFilter] = useState('')
  const [resultFilter, setResultFilter] = useState('')
  const [eventCategoryFilter, setEventCategoryFilter] = useState('')
  const [userFilter, setUserFilter] = useState('')
  const [sinceFilter, setSinceFilter] = useState('')
  const [untilFilter, setUntilFilter] = useState('')
  const [appliedEventFilters, setAppliedEventFilters] = useState<SecurityAuditEventFilters>({})
  const [events, setEvents] = useState<SecurityAuditEvent[]>([])
  const [eventsTotal, setEventsTotal] = useState(0)
  const [eventsLimit, setEventsLimit] = useState(limit)
  const [eventsLoading, setEventsLoading] = useState(false)
  const [eventsError, setEventsError] = useState<string | null>(null)
  const [retentionKeepLatest, setRetentionKeepLatest] = useState('200')
  const [retentionLoading, setRetentionLoading] = useState<'preview' | 'cleanup' | null>(null)
  const [retentionResult, setRetentionResult] = useState<SecurityAuditCleanupResponse | null>(null)
  const [retentionError, setRetentionError] = useState<string | null>(null)

  const applyLoadedEvents = useCallback((payload: LoadedSecurityAuditEventsState) => {
    setEvents(payload.events)
    setEventsTotal(payload.total)
    setEventsLimit(payload.limit)
  }, [])

  const loadEvents = useCallback(async (nextLimit = limit, nextFilters = appliedEventFilters) => {
    setEventsLoading(true)
    setEventsError(null)
    try {
      const payload = await loadSecurityAuditEventsState(nextLimit, nextFilters)
      applyLoadedEvents(payload)
    } catch (err) {
      setEventsError(normalizeAuditEventsLoadError(err))
    } finally {
      setEventsLoading(false)
    }
  }, [appliedEventFilters, applyLoadedEvents, limit])

  useEffect(() => {
    void loadEvents(limit, appliedEventFilters)
  }, [appliedEventFilters, limit, loadEvents])

  const draftEventFilters = useMemo(
    () => buildDraftAuditEventFilters({
      actionFilter,
      resultFilter,
      categoryFilter: eventCategoryFilter,
      userFilter,
      sinceFilter,
      untilFilter,
    }),
    [actionFilter, eventCategoryFilter, resultFilter, sinceFilter, untilFilter, userFilter],
  )
  const eventFiltersActive = hasAuditEventFilters(appliedEventFilters)
  const keepLatestNumber = parseRetentionKeepLatest(retentionKeepLatest)

  const applyEventFilters = useCallback(() => {
    setAppliedEventFilters(draftEventFilters)
  }, [draftEventFilters])

  const resetEventFilters = useCallback(() => {
    setActionFilter('')
    setResultFilter('')
    setEventCategoryFilter('')
    setUserFilter('')
    setSinceFilter('')
    setUntilFilter('')
    setAppliedEventFilters({})
  }, [])

  const selectActionFilter = useCallback((action: string) => {
    setActionFilter(action)
    setAppliedEventFilters(buildDraftAuditEventFilters({
      actionFilter: action,
      resultFilter,
      categoryFilter: eventCategoryFilter,
      userFilter,
      sinceFilter,
      untilFilter,
    }))
  }, [eventCategoryFilter, resultFilter, sinceFilter, untilFilter, userFilter])

  const refreshEvents = useCallback(() => {
    void loadEvents()
  }, [loadEvents])

  const previewRetentionCleanup = useCallback(() => {
    setRetentionError(null)
    setRetentionResult(buildRetentionPreview(eventsTotal, keepLatestNumber))
  }, [eventsTotal, keepLatestNumber])

  const runRetentionCleanup = useCallback(async () => {
    setRetentionLoading('cleanup')
    setRetentionError(null)
    try {
      const payload = await cleanupSecurityAuditEventsState({
        keepLatest: keepLatestNumber,
        onSummaryRefresh,
      })
      setRetentionResult(payload)
      await loadEvents(limit, appliedEventFilters)
    } catch (err) {
      setRetentionError(normalizeAuditEventsCleanupError(err))
    } finally {
      setRetentionLoading(null)
    }
  }, [appliedEventFilters, keepLatestNumber, limit, loadEvents, onSummaryRefresh])

  const eventsPanelProps = useMemo<SecurityAuditEventsPanelProps>(
    () =>
      createSecurityAuditEventsPanelProps(
        {
          events,
          eventsTotal,
          eventsLimit,
          eventsLoading,
          eventsError,
          actionFilter,
          resultFilter,
          categoryFilter: eventCategoryFilter,
          userFilter,
          sinceFilter,
          untilFilter,
          resultOptions,
          resetDisabled: !eventFiltersActive && !hasAuditEventFilters(draftEventFilters),
          retentionKeepLatest,
          retentionLoading,
          retentionResult,
          retentionError,
        },
        {
          onActionFilterChange: setActionFilter,
          onResultFilterChange: setResultFilter,
          onCategoryFilterChange: setEventCategoryFilter,
          onUserFilterChange: setUserFilter,
          onSinceFilterChange: setSinceFilter,
          onUntilFilterChange: setUntilFilter,
          onApplyFilters: applyEventFilters,
          onResetFilters: resetEventFilters,
          onRefresh: refreshEvents,
          onKeepLatestChange: setRetentionKeepLatest,
          onPreviewRetention: previewRetentionCleanup,
          onCleanupRetention: runRetentionCleanup,
        },
      ),
    [
      actionFilter,
      applyEventFilters,
      draftEventFilters,
      eventCategoryFilter,
      eventFiltersActive,
      events,
      eventsError,
      eventsLimit,
      eventsLoading,
      eventsTotal,
      previewRetentionCleanup,
      refreshEvents,
      resetEventFilters,
      resultFilter,
      resultOptions,
      retentionError,
      retentionKeepLatest,
      retentionLoading,
      retentionResult,
      runRetentionCleanup,
      sinceFilter,
      untilFilter,
      userFilter,
    ],
  )

  return {
    eventsPanelProps,
    selectedAction: appliedEventFilters.action,
    onSelectAction: selectActionFilter,
  }
}
