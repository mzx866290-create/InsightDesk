import { useCallback, useMemo, useState } from 'react'
import type { IntegratorScheduleTickResponse } from '../../api/client'
import type { ConnectorDraft } from './integratorConnectorModel'
import {
  dryRunIntegratorScheduleTick,
  loadIntegratorSchedules,
  saveIntegratorScheduleDrafts,
  triggerIntegratorScheduleById,
} from './integratorScheduleActions'
import {
  clampScheduleIndex,
  createScheduleDraft,
  formatScheduleActionError,
  getSavedScheduleId,
  nextSelectedIndexAfterRemove,
} from './integratorScheduleHookModel'
import * as integratorScheduleModel from './integratorScheduleModel'
import type { ScheduleDraft, ScheduleRuntime } from './integratorScheduleModel'

export interface UseIntegratorSchedulesResult {
  schedules: ScheduleDraft[]
  selectedScheduleIndex: number
  selectedSchedule: ScheduleDraft | null
  scheduleRuntime: ScheduleRuntime | null
  scheduleTickResult: IntegratorScheduleTickResponse | null
  scheduleValidationErrors: string[]
  scheduleLoading: boolean
  scheduleSaving: boolean
  scheduleTicking: boolean
  triggeringScheduleId: string | null
  scheduleError: string | null
  scheduleNotice: string | null
  setSelectedScheduleIndex: React.Dispatch<React.SetStateAction<number>>
  loadSchedules: () => Promise<void>
  updateSchedule: (index: number, patch: Partial<ScheduleDraft>) => void
  addSchedule: () => void
  removeSchedule: (index: number) => void
  handleSaveSchedules: () => Promise<void>
  handleTriggerSchedule: (schedule: ScheduleDraft) => Promise<void>
  handleDryRunScheduleTick: () => Promise<void>
}

export function useIntegratorSchedules(connectors: ConnectorDraft[]): UseIntegratorSchedulesResult {
  const [schedules, setSchedules] = useState<ScheduleDraft[]>([])
  const [selectedScheduleIndex, setSelectedScheduleIndex] = useState(0)
  const [scheduleRuntime, setScheduleRuntime] = useState<ScheduleRuntime | null>(null)
  const [scheduleTickResult, setScheduleTickResult] = useState<IntegratorScheduleTickResponse | null>(null)
  const [scheduleLoading, setScheduleLoading] = useState(false)
  const [scheduleSaving, setScheduleSaving] = useState(false)
  const [scheduleTicking, setScheduleTicking] = useState(false)
  const [triggeringScheduleId, setTriggeringScheduleId] = useState<string | null>(null)
  const [scheduleError, setScheduleError] = useState<string | null>(null)
  const [scheduleNotice, setScheduleNotice] = useState<string | null>(null)

  const selectedSchedule = schedules[selectedScheduleIndex] ?? null
  const scheduleValidationErrors = useMemo(
    () => integratorScheduleModel.scheduleValidationMessages(schedules),
    [schedules],
  )

  const loadSchedules = useCallback(async () => {
    setScheduleLoading(true)
    setScheduleError(null)
    setScheduleNotice(null)
    try {
      const payload = await loadIntegratorSchedules()
      setSchedules(payload.schedules)
      setScheduleRuntime(payload.scheduler ?? null)
      setScheduleTickResult(null)
      setSelectedScheduleIndex(0)
    } catch (err) {
      setScheduleError(formatScheduleActionError(err, 'Failed to load integration schedules'))
    } finally {
      setScheduleLoading(false)
    }
  }, [])

  const updateSchedule = useCallback((index: number, patch: Partial<ScheduleDraft>) => {
    setScheduleError(null)
    setScheduleNotice(null)
    setScheduleTickResult(null)
    setSchedules((current) =>
      current.map((schedule, itemIndex) =>
        itemIndex === index ? { ...schedule, ...patch } : schedule,
      ),
    )
  }, [])

  const addSchedule = useCallback(() => {
    setSchedules((current) => {
      const next = [...current, createScheduleDraft(current.length, connectors)]
      setSelectedScheduleIndex(next.length - 1)
      return next
    })
    setScheduleError(null)
    setScheduleNotice(null)
    setScheduleTickResult(null)
  }, [connectors])

  const removeSchedule = useCallback((index: number) => {
    setSchedules((current) => current.filter((_, itemIndex) => itemIndex !== index))
    setSelectedScheduleIndex((current) => nextSelectedIndexAfterRemove(current, schedules.length))
    setScheduleNotice(null)
    setScheduleTickResult(null)
  }, [schedules.length])

  const handleSaveSchedules = useCallback(async () => {
    if (scheduleValidationErrors.length > 0) {
      setScheduleError(scheduleValidationErrors[0])
      setScheduleNotice(null)
      return
    }

    setScheduleSaving(true)
    setScheduleError(null)
    setScheduleNotice(null)
    try {
      const payload = await saveIntegratorScheduleDrafts(schedules)
      setSchedules(payload.schedules)
      setSelectedScheduleIndex((index) => clampScheduleIndex(index, payload.schedules.length))
      setScheduleNotice('Integration schedules saved')
    } catch (err) {
      setScheduleError(formatScheduleActionError(err, 'Failed to save integration schedules'))
    } finally {
      setScheduleSaving(false)
    }
  }, [scheduleValidationErrors, schedules])

  const handleTriggerSchedule = useCallback(async (schedule: ScheduleDraft) => {
    const scheduleId = getSavedScheduleId(schedule)
    if (!scheduleId) {
      setScheduleError('Save the schedule before triggering it manually.')
      return
    }

    setTriggeringScheduleId(scheduleId)
    setScheduleError(null)
    setScheduleNotice(null)
    try {
      const payload = await triggerIntegratorScheduleById(scheduleId)
      await loadSchedules()
      setScheduleNotice(`Schedule trigger ${payload.status}`)
    } catch (err) {
      setScheduleError(formatScheduleActionError(err, 'Failed to trigger integration schedule'))
    } finally {
      setTriggeringScheduleId(null)
    }
  }, [loadSchedules])

  const handleDryRunScheduleTick = useCallback(async () => {
    setScheduleTicking(true)
    setScheduleError(null)
    setScheduleNotice(null)
    setScheduleTickResult(null)
    try {
      const payload = await dryRunIntegratorScheduleTick()
      setScheduleTickResult(payload)
      setScheduleNotice(`Dry-run tick scanned ${payload.checked} schedules`)
    } catch (err) {
      setScheduleError(formatScheduleActionError(err, 'Failed to scan integration schedules'))
    } finally {
      setScheduleTicking(false)
    }
  }, [])

  return {
    schedules,
    selectedScheduleIndex,
    selectedSchedule,
    scheduleRuntime,
    scheduleTickResult,
    scheduleValidationErrors,
    scheduleLoading,
    scheduleSaving,
    scheduleTicking,
    triggeringScheduleId,
    scheduleError,
    scheduleNotice,
    setSelectedScheduleIndex,
    loadSchedules,
    updateSchedule,
    addSchedule,
    removeSchedule,
    handleSaveSchedules,
    handleTriggerSchedule,
    handleDryRunScheduleTick,
  }
}
