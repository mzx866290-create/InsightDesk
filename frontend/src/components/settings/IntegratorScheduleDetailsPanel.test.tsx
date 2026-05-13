import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ConnectorDraft } from './integratorConnectorModel'
import type { ScheduleDraft, ScheduleRuntime } from './integratorScheduleModel'
import { IntegratorScheduleDetailsPanel } from './IntegratorScheduleDetailsPanel'

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

const schedule: ScheduleDraft = {
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

const scheduleRuntime: ScheduleRuntime = {
  mode: 'polling',
  automatic_dispatch: true,
  manual_trigger_supported: true,
}

describe('IntegratorScheduleDetailsPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders selected schedule details and forwards edits, trigger, and remove actions', () => {
    const onUpdateSchedule = vi.fn()
    const onTriggerSchedule = vi.fn()
    const onRemoveSchedule = vi.fn()

    render(
      <IntegratorScheduleDetailsPanel
        selectedSchedule={schedule}
        selectedScheduleIndex={0}
        connectors={connectors}
        scheduleRuntime={scheduleRuntime}
        scheduleLoading={false}
        triggeringScheduleId={null}
        onRemoveSchedule={onRemoveSchedule}
        onUpdateSchedule={onUpdateSchedule}
        onTriggerSchedule={onTriggerSchedule}
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

    expect(onTriggerSchedule).toHaveBeenCalledWith(schedule)
    expect(onRemoveSchedule).toHaveBeenCalledWith(0)
  })

  it('shows loading and empty details states', () => {
    const { rerender } = render(
      <IntegratorScheduleDetailsPanel
        selectedSchedule={null}
        selectedScheduleIndex={0}
        connectors={connectors}
        scheduleRuntime={scheduleRuntime}
        scheduleLoading={true}
        triggeringScheduleId={null}
        onRemoveSchedule={vi.fn()}
        onUpdateSchedule={vi.fn()}
        onTriggerSchedule={vi.fn()}
      />,
    )

    expect(screen.getByText('Loading schedules...')).toBeInTheDocument()

    rerender(
      <IntegratorScheduleDetailsPanel
        selectedSchedule={null}
        selectedScheduleIndex={0}
        connectors={connectors}
        scheduleRuntime={scheduleRuntime}
        scheduleLoading={false}
        triggeringScheduleId={null}
        onRemoveSchedule={vi.fn()}
        onUpdateSchedule={vi.fn()}
        onTriggerSchedule={vi.fn()}
      />,
    )

    expect(screen.getByText('No schedule selected')).toBeInTheDocument()
  })

  it('shows unsupported manual trigger state', () => {
    render(
      <IntegratorScheduleDetailsPanel
        selectedSchedule={schedule}
        selectedScheduleIndex={0}
        connectors={connectors}
        scheduleRuntime={{ ...scheduleRuntime, manual_trigger_supported: false }}
        scheduleLoading={false}
        triggeringScheduleId={null}
        onRemoveSchedule={vi.fn()}
        onUpdateSchedule={vi.fn()}
        onTriggerSchedule={vi.fn()}
      />,
    )

    expect(screen.getByText(/Manual trigger:/)).toHaveTextContent('Unsupported')
  })
})
