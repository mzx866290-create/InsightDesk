import React from 'react'
import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { IntegratorScheduleTickResponse, IntegratorSchedulesResponse } from '../../api/client'
import type { ConnectorDraft } from './integratorConnectorModel'
import type { ScheduleDraft } from './integratorScheduleModel'
import { useIntegratorSchedules } from './useIntegratorSchedules'

const mocks = vi.hoisted(() => ({
  getIntegratorSchedules: vi.fn(),
  saveIntegratorSchedules: vi.fn(),
  triggerIntegratorSchedule: vi.fn(),
  triggerIntegratorScheduleTick: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return {
    ...actual,
    getIntegratorSchedules: mocks.getIntegratorSchedules,
    saveIntegratorSchedules: mocks.saveIntegratorSchedules,
    triggerIntegratorSchedule: mocks.triggerIntegratorSchedule,
    triggerIntegratorScheduleTick: mocks.triggerIntegratorScheduleTick,
  }
})

const connectors: ConnectorDraft[] = [
  {
    id: 'connector-1',
    type: 'webhook',
    name: 'Ops Webhook',
    description: '',
    enabled: true,
    approved: true,
    settings: {},
    settingsJson: '{}',
  },
  {
    id: 'connector-2',
    type: 'email',
    name: 'Digest Email',
    description: '',
    enabled: true,
    approved: true,
    settings: {},
    settingsJson: '{}',
  },
]

const scheduleA: ScheduleDraft = {
  schedule_id: 'schedule-1',
  name: 'Nightly sync',
  connector_id: 'connector-1',
  cron: '0 1 * * *',
  timezone: 'Asia/Shanghai',
  interval_minutes: 60,
  enabled: true,
  settings: {},
  last_run_at: 1_715_000_000,
  next_run_at: 1_715_003_600,
}

const scheduleB: ScheduleDraft = {
  schedule_id: 'schedule-2',
  name: 'Digest sync',
  connector_id: 'connector-2',
  cron: '0 8 * * 1-5',
  timezone: 'UTC',
  interval_minutes: 120,
  enabled: false,
  settings: {},
  last_run_at: null,
  next_run_at: null,
}

const scheduleResponse = {
  schedules: [scheduleA, scheduleB],
  total: 2,
  scheduler: {
    mode: 'polling',
    automatic_dispatch: true,
    manual_trigger_supported: true,
  },
} satisfies IntegratorSchedulesResponse

describe('useIntegratorSchedules', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('loads schedules successfully and resets selected state', async () => {
    mocks.getIntegratorSchedules.mockResolvedValue(scheduleResponse)

    const { result } = renderHook(() => useIntegratorSchedules(connectors))

    await act(async () => {
      await result.current.loadSchedules()
    })

    await waitFor(() => {
      expect(result.current.scheduleLoading).toBe(false)
    })

    expect(mocks.getIntegratorSchedules).toHaveBeenCalledTimes(1)
    expect(result.current.schedules).toEqual([scheduleA, scheduleB])
    expect(result.current.scheduleRuntime).toEqual(scheduleResponse.scheduler)
    expect(result.current.scheduleTickResult).toBeNull()
    expect(result.current.selectedScheduleIndex).toBe(0)
    expect(result.current.selectedSchedule).toEqual(scheduleA)
    expect(result.current.scheduleError).toBeNull()
  })

  it('captures load failures', async () => {
    mocks.getIntegratorSchedules.mockRejectedValue(new Error('load failed'))

    const { result } = renderHook(() => useIntegratorSchedules(connectors))

    await act(async () => {
      await result.current.loadSchedules()
    })

    expect(result.current.scheduleError).toBe('load failed')
    expect(result.current.scheduleLoading).toBe(false)
  })

  it('adds, updates, and removes schedules', async () => {
    const { result } = renderHook(() => useIntegratorSchedules(connectors))

    act(() => {
      result.current.addSchedule()
    })

    expect(result.current.schedules).toHaveLength(1)
    expect(result.current.schedules[0].name).toBe('Sync schedule 1')
    expect(result.current.schedules[0].connector_id).toBe('connector-1')
    expect(result.current.selectedScheduleIndex).toBe(0)

    act(() => {
      result.current.updateSchedule(0, { name: 'Updated schedule', enabled: false })
    })

    expect(result.current.schedules[0].name).toBe('Updated schedule')
    expect(result.current.schedules[0].enabled).toBe(false)
    expect(result.current.scheduleError).toBeNull()
    expect(result.current.scheduleNotice).toBeNull()
    expect(result.current.scheduleTickResult).toBeNull()

    act(() => {
      result.current.addSchedule()
      result.current.addSchedule()
    })

    act(() => {
      result.current.setSelectedScheduleIndex(2)
      result.current.removeSchedule(1)
    })

    expect(result.current.schedules).toHaveLength(2)
    expect(result.current.selectedScheduleIndex).toBe(1)
    expect(result.current.scheduleNotice).toBeNull()
    expect(result.current.scheduleTickResult).toBeNull()
  })

  it('blocks save on validation and saves successfully', async () => {
    const { result } = renderHook(() => useIntegratorSchedules(connectors))

    act(() => {
      result.current.addSchedule()
      result.current.updateSchedule(0, { cron: '', interval_minutes: 1, timezone: 'Invalid/Timezone' })
    })

    await act(async () => {
      await result.current.handleSaveSchedules()
    })

    expect(mocks.saveIntegratorSchedules).not.toHaveBeenCalled()
    expect(result.current.scheduleError).toContain('Cron is required.')

    act(() => {
      result.current.updateSchedule(0, { cron: '0 * * * *', interval_minutes: 60, timezone: 'UTC' })
    })

    mocks.saveIntegratorSchedules.mockResolvedValue({
      schedules: [scheduleA],
    })

    await act(async () => {
      await result.current.handleSaveSchedules()
    })

    expect(mocks.saveIntegratorSchedules).toHaveBeenCalledTimes(1)
    expect(result.current.schedules).toEqual([scheduleA])
    expect(result.current.scheduleNotice).toBe('Integration schedules saved')
    expect(result.current.selectedScheduleIndex).toBe(0)
    expect(result.current.scheduleSaving).toBe(false)
  })

  it('triggers schedules and reports missing ids', async () => {
    const { result } = renderHook(() => useIntegratorSchedules(connectors))

    await act(async () => {
      await result.current.handleTriggerSchedule({ ...scheduleA, schedule_id: '' })
    })

    expect(result.current.scheduleError).toBe('Save the schedule before triggering it manually.')
    expect(mocks.triggerIntegratorSchedule).not.toHaveBeenCalled()

    mocks.getIntegratorSchedules.mockResolvedValue(scheduleResponse)
    mocks.triggerIntegratorSchedule.mockResolvedValue({ status: 'started' })

    await act(async () => {
      await result.current.handleTriggerSchedule(scheduleA)
    })

    expect(mocks.triggerIntegratorSchedule).toHaveBeenCalledWith('schedule-1')
    expect(mocks.getIntegratorSchedules).toHaveBeenCalledTimes(1)
    expect(result.current.scheduleNotice).toBe('Schedule trigger started')
    expect(result.current.triggeringScheduleId).toBeNull()
  })

  it('runs a dry-run tick and stores the result', async () => {
    const tickResult: IntegratorScheduleTickResponse = {
      dry_run: true,
      executed: false,
      checked: 6,
      due_count: 2,
      skipped: {
        disabled: 1,
        not_due: 3,
      },
      now: 1_715_000_000,
    }
    mocks.triggerIntegratorScheduleTick.mockResolvedValue(tickResult)

    const { result } = renderHook(() => useIntegratorSchedules(connectors))

    await act(async () => {
      await result.current.handleDryRunScheduleTick()
    })

    expect(mocks.triggerIntegratorScheduleTick).toHaveBeenCalledWith(true)
    expect(result.current.scheduleTickResult).toEqual(tickResult)
    expect(result.current.scheduleNotice).toBe('Dry-run tick scanned 6 schedules')
    expect(result.current.scheduleTicking).toBe(false)
  })
})
