import type { ScheduleDraft } from './integratorScheduleSharedModel'

export function scheduleDisplayName(schedule: ScheduleDraft): string {
  return schedule.name || schedule.schedule_id || 'schedule'
}

export function scheduleStatusTone(schedule: ScheduleDraft): string {
  return schedule.enabled ? 'bg-accent-green/15 text-accent-green' : 'bg-bg-hover text-text-secondary'
}

export function scheduleStatusLabel(schedule: ScheduleDraft): string {
  return schedule.enabled ? 'Enabled' : 'Disabled'
}
