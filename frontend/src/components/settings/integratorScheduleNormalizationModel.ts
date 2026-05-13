import type { IntegratorSchedule } from '../../api/client'

import type { ScheduleDraft } from './integratorScheduleSharedModel'

export function draftToSchedule(draft: ScheduleDraft): IntegratorSchedule {
  return {
    schedule_id: draft.schedule_id?.trim() || undefined,
    name: draft.name.trim() || 'Integrator schedule',
    connector_id: draft.connector_id.trim(),
    cron: draft.cron.trim() || '0 * * * *',
    timezone: normalizeScheduleTimezone(draft.timezone),
    interval_minutes: Math.trunc(Number(draft.interval_minutes) || 60),
    enabled: draft.enabled !== false,
    settings: draft.settings ?? {},
    last_run_at: draft.last_run_at ?? null,
    next_run_at: draft.next_run_at ?? null,
  }
}

export function normalizeScheduleTimezone(timezone: string | undefined): string {
  return timezone?.trim() || 'UTC'
}
