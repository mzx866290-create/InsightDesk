import type { IntegratorSchedule, IntegratorSchedulesResponse } from '../../api/client'

export type ScheduleDraft = IntegratorSchedule

export type ScheduleRuntime = NonNullable<IntegratorSchedulesResponse['scheduler']>

export const MIN_SCHEDULE_INTERVAL_MINUTES = 5
export const MAX_SCHEDULE_INTERVAL_MINUTES = 60 * 24 * 30

export const SCHEDULE_CRON_PRESETS = [
  { value: '@hourly', label: 'Hourly' },
  { value: '@daily', label: 'Daily' },
  { value: '@weekly', label: 'Weekly' },
  { value: '@monthly', label: 'Monthly' },
  { value: '@yearly', label: 'Yearly' },
  { value: '0 9 ? * MON-FRI', label: 'Weekday 09:00' },
  { value: '0 0 1 * ?', label: 'Monthly midnight' },
] as const

export const COMMON_TIMEZONES = [
  'UTC',
  'Asia/Shanghai',
  'Asia/Tokyo',
  'Asia/Singapore',
  'Europe/London',
  'Europe/Berlin',
  'America/New_York',
  'America/Chicago',
  'America/Los_Angeles',
  'Australia/Sydney',
] as const

export const DEFAULT_SCHEDULE: ScheduleDraft = {
  name: 'Hourly sync',
  connector_id: '',
  cron: '0 * * * *',
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
  interval_minutes: 60,
  enabled: true,
  settings: {},
  last_run_at: null,
  next_run_at: null,
}
