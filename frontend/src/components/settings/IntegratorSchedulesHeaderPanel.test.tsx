import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { IntegratorScheduleTickResponse } from '../../api/client'
import type { ScheduleRuntime } from './integratorScheduleModel'
import {
  IntegratorSchedulesHeaderPanel,
  type IntegratorSchedulesHeaderPanelProps,
} from './IntegratorSchedulesHeaderPanel'

vi.mock('../ui/Button', () => ({
  Button: ({
    children,
    loading: _loading,
    disabled,
    variant: _variant,
    size: _size,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    loading?: boolean
    variant?: string
    size?: string
  }) => (
    <button {...props} disabled={disabled || _loading}>
      {children}
    </button>
  ),
}))

function createProps(
  overrides: Partial<IntegratorSchedulesHeaderPanelProps> = {},
): IntegratorSchedulesHeaderPanelProps {
  const scheduleRuntime: ScheduleRuntime = {
    mode: 'polling',
    automatic_dispatch: true,
    manual_trigger_supported: true,
  }

  return {
    scheduleCount: 2,
    scheduleRuntime,
    scheduleTickResult: null,
    scheduleValidationErrors: [],
    scheduleNotice: null,
    scheduleError: null,
    scheduleLoading: false,
    scheduleSaving: false,
    scheduleTicking: false,
    onRefreshSchedules: vi.fn(),
    onDryRunScheduleTick: vi.fn(),
    onAddSchedule: vi.fn(),
    onSaveSchedules: vi.fn(),
    ...overrides,
  }
}

describe('IntegratorSchedulesHeaderPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('forwards toolbar actions and renders summary feedback', () => {
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

    render(<IntegratorSchedulesHeaderPanel {...props} />)

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

  it('prefers error over validation and disables save when validation exists', () => {
    render(
      <IntegratorSchedulesHeaderPanel
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

  it('shows loading state for the toolbar buttons', () => {
    render(
      <IntegratorSchedulesHeaderPanel
        {...createProps({
          scheduleLoading: true,
          scheduleSaving: true,
          scheduleTicking: true,
        })}
      />,
    )

    expect(screen.getByTestId('settings-integrator-schedules-refresh')).toBeDisabled()
    expect(screen.getByTestId('settings-integrator-schedule-tick')).toBeDisabled()
    expect(screen.getByTestId('settings-integrator-schedule-save')).toBeDisabled()
  })
})
