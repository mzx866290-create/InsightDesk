import React from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ScheduleDraft } from './integratorScheduleModel'
import { IntegratorScheduleListPanel } from './IntegratorScheduleListPanel'

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

describe('IntegratorScheduleListPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders schedule rows and forwards selection', () => {
    const onSelectSchedule = vi.fn()

    render(
      <IntegratorScheduleListPanel
        schedules={[scheduleA, scheduleB]}
        selectedScheduleIndex={1}
        scheduleError={null}
        scheduleLoading={false}
        onAddSchedule={vi.fn()}
        onSelectSchedule={onSelectSchedule}
      />,
    )

    const rows = screen.getAllByTestId('settings-integrator-schedule-row')
    expect(rows).toHaveLength(2)
    expect(within(rows[0]).getByTestId('settings-integrator-schedule-row-name')).toHaveTextContent('Nightly sync')
    expect(within(rows[0]).getByTestId('settings-integrator-schedule-row-status')).toHaveTextContent('Enabled')
    expect(within(rows[0]).getByTestId('settings-integrator-schedule-row-timezone')).toHaveTextContent('Asia/Shanghai')
    expect(within(rows[1]).getByTestId('settings-integrator-schedule-row-status')).toHaveTextContent('Disabled')
    expect(within(rows[1]).getByTestId('settings-integrator-schedule-row-interval')).toHaveTextContent('120m')

    fireEvent.click(rows[0])
    expect(onSelectSchedule).toHaveBeenCalledWith(0)
  })

  it('renders empty add action only when not loading or errored', () => {
    const onAddSchedule = vi.fn()
    const { rerender } = render(
      <IntegratorScheduleListPanel
        schedules={[]}
        selectedScheduleIndex={0}
        scheduleError={null}
        scheduleLoading={false}
        onAddSchedule={onAddSchedule}
        onSelectSchedule={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByTestId('settings-integrator-schedule-empty'))
    expect(onAddSchedule).toHaveBeenCalledTimes(1)

    rerender(
      <IntegratorScheduleListPanel
        schedules={[]}
        selectedScheduleIndex={0}
        scheduleError="Load failed"
        scheduleLoading={false}
        onAddSchedule={onAddSchedule}
        onSelectSchedule={vi.fn()}
      />,
    )

    expect(screen.queryByTestId('settings-integrator-schedule-empty')).not.toBeInTheDocument()
  })
})
