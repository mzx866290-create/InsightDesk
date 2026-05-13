import { describe, expect, it } from 'vitest'

import type { IntegratorSchedule } from '../../api/client'
import {
  draftToSchedule,
  scheduleDisplayName,
  scheduleStatusLabel,
  scheduleStatusTone,
  scheduleValidationMessages,
  validateScheduleCron,
  validateScheduleInterval,
  validateScheduleTimezone,
} from './integratorScheduleModel'

describe('integratorScheduleModel', () => {
  it('normalizes schedule drafts and validates cron, timezone, and interval rules', () => {
    const schedule: IntegratorSchedule = {
      schedule_id: ' sched-1 ',
      name: '  Nightly sync ',
      connector_id: ' conn-1 ',
      cron: '@weekly',
      timezone: ' UTC ',
      interval_minutes: 15,
      enabled: false,
      settings: { batch: true },
      last_run_at: 10,
      next_run_at: 20,
    }

    const draft = draftToSchedule(schedule)
    expect(draft).toEqual({
      schedule_id: 'sched-1',
      name: 'Nightly sync',
      connector_id: 'conn-1',
      cron: '@weekly',
      timezone: 'UTC',
      interval_minutes: 15,
      enabled: false,
      settings: { batch: true },
      last_run_at: 10,
      next_run_at: 20,
    })
    expect(scheduleDisplayName(draft)).toBe('Nightly sync')
    expect(scheduleStatusTone(draft)).toContain('text-text-secondary')
    expect(scheduleStatusLabel(draft)).toBe('Disabled')
    expect(validateScheduleCron('@weekly')).toBeNull()
    expect(validateScheduleCron('bad cron')).toContain('5 fields')
    expect(validateScheduleInterval(4)).toContain('at least 5 minutes')
    expect(validateScheduleTimezone('UTC')).toBeNull()
    expect(validateScheduleTimezone('Invalid/Zone')).toContain('valid IANA timezone')
    expect(scheduleValidationMessages([draft])).toEqual([])
  })
})
