import React from 'react'
import { CalendarClock, CheckCircle, Play, Plus, RefreshCw, Save } from 'lucide-react'

import type { IntegratorScheduleTickResponse } from '../../api/client'
import { Button } from '../ui/Button'
import type { ScheduleRuntime } from './integratorScheduleModel'

export interface IntegratorSchedulesHeaderPanelProps {
  scheduleCount: number
  scheduleRuntime: ScheduleRuntime | null
  scheduleTickResult: IntegratorScheduleTickResponse | null
  scheduleValidationErrors: string[]
  scheduleNotice: string | null
  scheduleError: string | null
  scheduleLoading: boolean
  scheduleSaving: boolean
  scheduleTicking: boolean
  onRefreshSchedules: () => void
  onDryRunScheduleTick: () => void
  onAddSchedule: () => void
  onSaveSchedules: () => void
}

export const IntegratorSchedulesHeaderPanel: React.FC<IntegratorSchedulesHeaderPanelProps> = ({
  scheduleCount,
  scheduleRuntime,
  scheduleTickResult,
  scheduleValidationErrors,
  scheduleNotice,
  scheduleError,
  scheduleLoading,
  scheduleSaving,
  scheduleTicking,
  onRefreshSchedules,
  onDryRunScheduleTick,
  onAddSchedule,
  onSaveSchedules,
}) => {
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h4 className="flex items-center gap-2 text-sm font-medium text-text-primary">
            <CalendarClock size={14} className="text-accent-blue" />
            Sync schedules
          </h4>
          <p className="mt-1 text-xs text-text-secondary">
            Manage scheduled connector syncs without exposing secret settings.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onRefreshSchedules}
            loading={scheduleLoading}
            data-testid="settings-integrator-schedules-refresh"
          >
            <RefreshCw size={12} />
            Refresh
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onDryRunScheduleTick}
            loading={scheduleTicking}
            data-testid="settings-integrator-schedule-tick"
          >
            <Play size={12} />
            Scan due
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onAddSchedule}
            data-testid="settings-integrator-schedule-add"
          >
            <Plus size={12} />
            Add
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={onSaveSchedules}
            loading={scheduleSaving}
            disabled={scheduleValidationErrors.length > 0}
            data-testid="settings-integrator-schedule-save"
          >
            <Save size={12} />
            Save schedules
          </Button>
        </div>
      </div>

      {scheduleNotice && (
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-accent-green/30 bg-accent-green/10 px-3 py-2 text-xs text-accent-green">
          <CheckCircle size={13} />
          {scheduleNotice}
        </div>
      )}

      {scheduleError && (
        <div
          className="mt-3 rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red"
          data-testid="settings-integrator-schedule-error"
        >
          {scheduleError}
        </div>
      )}

      {scheduleValidationErrors.length > 0 && !scheduleError && (
        <div
          className="mt-3 rounded-lg border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-xs text-amber-200"
          data-testid="settings-integrator-schedule-validation"
        >
          {scheduleValidationErrors[0]}
        </div>
      )}

      <div className="mt-3 grid gap-2 rounded-lg border border-bg-border bg-bg-secondary/30 px-3 py-2 text-[11px] text-text-secondary sm:grid-cols-3">
        <span>
          Total: <b className="text-text-primary">{scheduleCount}</b>
        </span>
        <span>
          Automatic dispatch:{' '}
          <b className="text-text-primary" data-testid="settings-integrator-schedule-auto-dispatch">
            {scheduleRuntime ? (scheduleRuntime.automatic_dispatch ? 'On' : 'Off') : '-'}
          </b>
        </span>
        <span>
          Scheduler:{' '}
          <b className="text-text-primary" data-testid="settings-integrator-schedule-mode">
            {scheduleRuntime?.mode ?? '-'}
          </b>
        </span>
      </div>

      {scheduleTickResult && (
        <div
          className="mt-3 grid gap-2 rounded-lg border border-bg-border bg-bg-tertiary/30 px-3 py-2 text-[11px] text-text-secondary sm:grid-cols-3"
          data-testid="settings-integrator-schedule-tick-result"
        >
          <span>
            Due:{' '}
            <b className="text-text-primary" data-testid="settings-integrator-schedule-tick-due-count">
              {scheduleTickResult.due_count}
            </b>
          </span>
          <span>
            Skipped:{' '}
            <b className="text-text-primary" data-testid="settings-integrator-schedule-tick-skipped">
              {scheduleTickResult.skipped.disabled + scheduleTickResult.skipped.not_due}
            </b>
          </span>
          <span>
            Mode:{' '}
            <b className="text-text-primary">{scheduleTickResult.dry_run ? 'Dry-run' : 'Run'}</b>
          </span>
        </div>
      )}
    </>
  )
}
