import React from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { IntegratorScheduleTickResponse } from '../../api/client'
import type { ConnectorDraft } from './integratorConnectorModel'
import type { ScheduleDraft, ScheduleRuntime } from './integratorScheduleModel'
import {
  IntegratorSchedulesPanel,
  type IntegratorSchedulesPanelProps,
} from './IntegratorSchedulesPanel'

vi.mock('../ui/Button', () => ({
  Button: ({
    children,
    loading: _loading,
    variant: _variant,
    size: _size,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    loading?: boolean
    variant?: string
    size?: string
  }) => (
    <button {...props}>{children}</button>
  ),
}))

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

const scheduleRuntime: ScheduleRuntime = {
  mode: 'polling',
  automatic_dispatch: true,
  manual_trigger_supported: true,
}

function createProps(overrides: Partial<IntegratorSchedulesPanelProps> = {}): IntegratorSchedulesPanelProps {
  return {
    schedules: [scheduleA, scheduleB],
    selectedScheduleIndex: 0,
    selectedSchedule: scheduleA,
    connectors,
    scheduleRuntime,
    scheduleTickResult: null,
    scheduleValidationErrors: [],
    scheduleNotice: null,
    scheduleError: null,
    scheduleLoading: false,
    scheduleSaving: false,
    scheduleTicking: false,
    triggeringScheduleId: null,
    onRefreshSchedules: vi.fn(),
    onDryRunScheduleTick: vi.fn(),
    onAddSchedule: vi.fn(),
    onSaveSchedules: vi.fn(),
    onSelectSchedule: vi.fn(),
    onRemoveSchedule: vi.fn(),
    onUpdateSchedule: vi.fn(),
    onTriggerSchedule: vi.fn(),
    ...overrides,
  }
}

describe('IntegratorSchedulesPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders the toolbar, summary, tick result, and forwards toolbar actions', () => {
    const props = createProps({
      scheduleNotice: 'Integration schedules saved',
      scheduleTickResult: {
        dry_run: true,
        executed: false,
        checked: 6,
        due_count: 2,
        skipped: {
          disabled: 1,
          not_due: 3,
        },
        now: 1_715_000_000,
      } satisfies IntegratorScheduleTickResponse,
    })

    render(<IntegratorSchedulesPanel {...props} />)

    expect(screen.getByTestId('settings-integrator-schedules-panel')).toBeInTheDocument()
    expect(screen.getByTestId('settings-integrator-schedule-auto-dispatch')).toHaveTextContent('On')
    expect(screen.getByTestId('settings-integrator-schedule-mode')).toHaveTextContent('polling')
    expect(screen.getByTestId('settings-integrator-schedule-tick-result')).toHaveTextContent('Due: 2')
    expect(screen.getByTestId('settings-integrator-schedule-tick-result')).toHaveTextContent('Skipped: 4')
    expect(screen.getByTestId('settings-integrator-schedule-tick-result')).toHaveTextContent('Mode: Dry-run')
    expect(screen.getByText('Integration schedules saved')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('settings-integrator-schedules-refresh'))
    fireEvent.click(screen.getByTestId('settings-integrator-schedule-tick'))
    fireEvent.click(screen.getByTestId('settings-integrator-schedule-add'))
    fireEvent.click(screen.getByTestId('settings-integrator-schedule-save'))

    expect(props.onRefreshSchedules).toHaveBeenCalledTimes(1)
    expect(props.onDryRunScheduleTick).toHaveBeenCalledTimes(1)
    expect(props.onAddSchedule).toHaveBeenCalledTimes(1)
    expect(props.onSaveSchedules).toHaveBeenCalledTimes(1)
  })

  it('disables save when validation errors exist and prefers error over validation', () => {
    render(
      <IntegratorSchedulesPanel
        {...createProps({
          scheduleNotice: 'Saved',
          scheduleError: 'Save failed',
          scheduleValidationErrors: ['Nightly sync: Cron is required.'],
        })}
      />,
    )

    expect(screen.getByTestId('settings-integrator-schedule-save')).toBeDisabled()
    expect(screen.getByTestId('settings-integrator-schedule-error')).toHaveTextContent('Save failed')
    expect(screen.queryByTestId('settings-integrator-schedule-validation')).not.toBeInTheDocument()
    expect(screen.getByText('Saved')).toBeInTheDocument()
  })

  it('renders the empty state and forwards add action', () => {
    const onAddSchedule = vi.fn()

    render(
      <IntegratorSchedulesPanel
        {...createProps({
          schedules: [],
          selectedScheduleIndex: 0,
          selectedSchedule: null,
          scheduleRuntime: null,
          onAddSchedule,
        })}
      />,
    )

    fireEvent.click(screen.getByTestId('settings-integrator-schedule-empty'))
    expect(onAddSchedule).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('settings-integrator-schedule-empty')).toHaveTextContent('Add the first sync schedule')
  })

  it('renders rows with status, name, timezone, and selection behavior', () => {
    const onSelectSchedule = vi.fn()

    render(
      <IntegratorSchedulesPanel
        {...createProps({
          selectedScheduleIndex: 1,
          selectedSchedule: scheduleB,
          onSelectSchedule,
        })}
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

  it('renders selected schedule details and forwards edits, trigger, and remove actions', () => {
    const onUpdateSchedule = vi.fn()
    const onTriggerSchedule = vi.fn()
    const onRemoveSchedule = vi.fn()

    render(
      <IntegratorSchedulesPanel
        {...createProps({
          selectedScheduleIndex: 0,
          selectedSchedule: scheduleA,
          onUpdateSchedule,
          onTriggerSchedule,
          onRemoveSchedule,
        })}
      />,
    )

    expect(screen.getByTestId('settings-integrator-schedule-name')).toHaveValue('Nightly sync')
    expect(screen.getByTestId('settings-integrator-schedule-connector')).toHaveValue('connector-1')
    expect(screen.getByTestId('settings-integrator-schedule-cron')).toHaveValue('0 1 * * *')
    expect(screen.getByTestId('settings-integrator-schedule-interval')).toHaveValue(60)
    expect(screen.getByTestId('settings-integrator-schedule-timezone-display')).toHaveTextContent('Asia/Shanghai')
    expect(screen.getByText(/Manual trigger:/)).toHaveTextContent('Supported')

    fireEvent.change(screen.getByTestId('settings-integrator-schedule-name'), {
      target: { value: 'Updated sync' },
    })
    fireEvent.change(screen.getByTestId('settings-integrator-schedule-connector'), {
      target: { value: 'connector-2' },
    })
    fireEvent.change(screen.getByTestId('settings-integrator-schedule-cron'), {
      target: { value: '*/10 * * * *' },
    })
    fireEvent.change(screen.getByTestId('settings-integrator-schedule-interval'), {
      target: { value: '90' },
    })
    fireEvent.change(screen.getByTestId('settings-integrator-schedule-timezone'), {
      target: { value: 'UTC' },
    })
    fireEvent.click(screen.getByTestId('settings-integrator-schedule-enabled'))

    expect(onUpdateSchedule).toHaveBeenNthCalledWith(1, 0, { name: 'Updated sync' })
    expect(onUpdateSchedule).toHaveBeenNthCalledWith(2, 0, { connector_id: 'connector-2' })
    expect(onUpdateSchedule).toHaveBeenNthCalledWith(3, 0, { cron: '*/10 * * * *' })
    expect(onUpdateSchedule).toHaveBeenNthCalledWith(4, 0, { interval_minutes: 90 })
    expect(onUpdateSchedule).toHaveBeenNthCalledWith(5, 0, { timezone: 'UTC' })
    expect(onUpdateSchedule).toHaveBeenNthCalledWith(6, 0, { enabled: false })

    fireEvent.click(screen.getByTestId('settings-integrator-schedule-trigger'))
    fireEvent.click(screen.getByTestId('settings-integrator-schedule-remove'))

    expect(onTriggerSchedule).toHaveBeenCalledWith(scheduleA)
    expect(onRemoveSchedule).toHaveBeenCalledWith(0)
  })

  it('shows loading and empty details states and manual trigger unsupported text', () => {
    const { rerender } = render(
      <IntegratorSchedulesPanel
        {...createProps({
          selectedSchedule: null,
          scheduleLoading: true,
          scheduleRuntime: {
            mode: 'polling',
            automatic_dispatch: false,
            manual_trigger_supported: false,
          },
        })}
      />,
    )

    expect(screen.getByText('Loading schedules...')).toBeInTheDocument()

    rerender(
      <IntegratorSchedulesPanel
        {...createProps({
          selectedSchedule: null,
          scheduleLoading: false,
          scheduleRuntime: {
            mode: 'polling',
            automatic_dispatch: false,
            manual_trigger_supported: false,
          },
        })}
      />,
    )

    expect(screen.getByText('No schedule selected')).toBeInTheDocument()
  })
})
