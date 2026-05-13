import {
  getIntegratorSchedules,
  saveIntegratorSchedules,
  triggerIntegratorSchedule,
  triggerIntegratorScheduleTick,
} from '../../api/client'
import type {
  IntegratorScheduleTickResponse,
  IntegratorSchedulesResponse,
} from '../../api/client'
import * as integratorScheduleModel from './integratorScheduleModel'
import type { ScheduleDraft } from './integratorScheduleModel'

export function loadIntegratorSchedules(): Promise<IntegratorSchedulesResponse> {
  return getIntegratorSchedules()
}

export function saveIntegratorScheduleDrafts(
  schedules: ScheduleDraft[],
): Promise<Pick<IntegratorSchedulesResponse, 'schedules'>> {
  return saveIntegratorSchedules(schedules.map(integratorScheduleModel.draftToSchedule))
}

export function triggerIntegratorScheduleById(scheduleId: string): Promise<{ status: string }> {
  return triggerIntegratorSchedule(scheduleId)
}

export function dryRunIntegratorScheduleTick(): Promise<IntegratorScheduleTickResponse> {
  // The settings UI intentionally scans only in dry-run mode; real dispatch belongs to the scheduler.
  return triggerIntegratorScheduleTick(true)
}
