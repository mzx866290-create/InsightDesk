import type { ConnectorDraft } from './integratorConnectorModel'
import * as integratorScheduleModel from './integratorScheduleModel'
import type { ScheduleDraft } from './integratorScheduleModel'

export function formatScheduleActionError(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : String(err || fallback)
}

export function createScheduleDraft(scheduleCount: number, connectors: ConnectorDraft[]): ScheduleDraft {
  return {
    ...integratorScheduleModel.DEFAULT_SCHEDULE,
    name: `Sync schedule ${scheduleCount + 1}`,
    connector_id: connectors[0]?.id ?? connectors[0]?.name ?? '',
  }
}

export function clampScheduleIndex(index: number, scheduleCount: number): number {
  return Math.max(0, Math.min(index, scheduleCount - 1))
}

export function nextSelectedIndexAfterRemove(index: number, scheduleCountBeforeRemove: number): number {
  return clampScheduleIndex(index, scheduleCountBeforeRemove - 1)
}

export function getSavedScheduleId(schedule: ScheduleDraft): string | null {
  const scheduleId = schedule.schedule_id?.trim()
  return scheduleId || null
}
