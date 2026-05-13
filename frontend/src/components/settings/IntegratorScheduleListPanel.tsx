import React from 'react'

import {
  normalizeScheduleTimezone,
  scheduleDisplayName,
  scheduleStatusLabel,
  scheduleStatusTone,
  type ScheduleDraft,
} from './integratorScheduleModel'

export interface IntegratorScheduleListPanelProps {
  schedules: ScheduleDraft[]
  selectedScheduleIndex: number
  scheduleError: string | null
  scheduleLoading: boolean
  onAddSchedule: () => void
  onSelectSchedule: (index: number) => void
}

export const IntegratorScheduleListPanel: React.FC<IntegratorScheduleListPanelProps> = ({
  schedules,
  selectedScheduleIndex,
  scheduleError,
  scheduleLoading,
  onAddSchedule,
  onSelectSchedule,
}) => (
  <div className="space-y-2">
    {!scheduleError && schedules.length === 0 && !scheduleLoading && (
      <button
        type="button"
        onClick={onAddSchedule}
        className="w-full rounded-lg border border-dashed border-bg-border bg-bg-secondary/30 px-3 py-6 text-center text-xs text-text-secondary hover:border-accent-blue/40 hover:text-text-primary"
        data-testid="settings-integrator-schedule-empty"
      >
        Add the first sync schedule
      </button>
    )}

    {schedules.map((schedule, index) => (
      <button
        key={`${schedule.schedule_id || schedule.name || 'schedule'}-${index}`}
        type="button"
        onClick={() => onSelectSchedule(index)}
        data-testid="settings-integrator-schedule-row"
        data-schedule-id={schedule.schedule_id ?? ''}
        className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
          selectedScheduleIndex === index
            ? 'border-accent-blue/50 bg-accent-blue/10'
            : 'border-bg-border bg-bg-secondary/40 hover:border-accent-blue/30'
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <span
            className="min-w-0 truncate text-sm font-medium text-text-primary"
            data-testid="settings-integrator-schedule-row-name"
          >
            {scheduleDisplayName(schedule)}
          </span>
          <span
            className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] ${scheduleStatusTone(schedule)}`}
            data-testid="settings-integrator-schedule-row-status"
          >
            {scheduleStatusLabel(schedule)}
          </span>
        </div>
        <div className="mt-1 flex items-center justify-between gap-2 text-[11px] text-text-secondary">
          <span>{schedule.connector_id || 'No connector'}</span>
          <span>
            {schedule.cron} /{' '}
            <span data-testid="settings-integrator-schedule-row-interval">
              {schedule.interval_minutes}m
            </span>{' '}
            /{' '}
            <span data-testid="settings-integrator-schedule-row-timezone">
              {normalizeScheduleTimezone(schedule.timezone)}
            </span>
          </span>
        </div>
      </button>
    ))}
  </div>
)
