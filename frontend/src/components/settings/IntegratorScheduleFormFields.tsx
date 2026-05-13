import React from 'react'

import { displayName, type ConnectorDraft } from './integratorConnectorModel'
import {
  COMMON_TIMEZONES,
  MAX_SCHEDULE_INTERVAL_MINUTES,
  MIN_SCHEDULE_INTERVAL_MINUTES,
  SCHEDULE_CRON_PRESETS,
  type ScheduleDraft,
  type ScheduleRuntime,
} from './integratorScheduleModel'

interface IntegratorScheduleFormFieldsProps {
  connectors: ConnectorDraft[]
  schedule: ScheduleDraft
  scheduleIndex: number
  scheduleRuntime: ScheduleRuntime | null
  onUpdateSchedule: (index: number, patch: Partial<ScheduleDraft>) => void
}

export const IntegratorScheduleFormFields: React.FC<IntegratorScheduleFormFieldsProps> = ({
  connectors,
  schedule,
  scheduleIndex,
  scheduleRuntime,
  onUpdateSchedule,
}) => (
  <>
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="space-y-1 text-xs text-text-secondary">
        Name
        <input
          className="input-base h-9 w-full"
          value={schedule.name}
          onChange={(event) => onUpdateSchedule(scheduleIndex, { name: event.target.value })}
          data-testid="settings-integrator-schedule-name"
        />
      </label>
      <label className="space-y-1 text-xs text-text-secondary">
        Connector
        <select
          className="input-base h-9 w-full"
          value={schedule.connector_id}
          onChange={(event) => onUpdateSchedule(scheduleIndex, { connector_id: event.target.value })}
          data-testid="settings-integrator-schedule-connector"
        >
          <option value="">Select connector</option>
          {connectors.map((connector, index) => {
            const connectorId = connector.id || connector.name || connector.type
            return (
              <option key={`${connectorId}-${index}`} value={connectorId}>
                {displayName(connector)}
              </option>
            )
          })}
        </select>
      </label>
    </div>

    <div className="grid gap-3 sm:grid-cols-2">
      <label className="space-y-1 text-xs text-text-secondary">
        Cron
        <input
          className="input-base h-9 w-full font-mono"
          list="integrator-schedule-cron-presets"
          value={schedule.cron}
          onChange={(event) => onUpdateSchedule(scheduleIndex, { cron: event.target.value })}
          data-testid="settings-integrator-schedule-cron"
        />
        <datalist id="integrator-schedule-cron-presets">
          {SCHEDULE_CRON_PRESETS.map((preset) => (
            <option key={preset.value} value={preset.value} label={preset.label} />
          ))}
        </datalist>
        <p className="text-[11px] text-text-secondary" data-testid="settings-integrator-schedule-cron-help">
          5-field cron, macros, and ? in day/weekday fields are supported.
        </p>
      </label>
      <label className="space-y-1 text-xs text-text-secondary">
        Interval minutes
        <input
          type="number"
          min={MIN_SCHEDULE_INTERVAL_MINUTES}
          max={MAX_SCHEDULE_INTERVAL_MINUTES}
          step={1}
          className="input-base h-9 w-full"
          value={schedule.interval_minutes}
          onChange={(event) =>
            onUpdateSchedule(scheduleIndex, {
              interval_minutes: Number(event.target.value),
            })
          }
          data-testid="settings-integrator-schedule-interval"
        />
      </label>
    </div>

    <div className="grid gap-3 sm:grid-cols-2">
      <label className="space-y-1 text-xs text-text-secondary">
        Timezone
        <input
          className="input-base h-9 w-full"
          list="integrator-schedule-timezones"
          value={schedule.timezone ?? ''}
          onChange={(event) => onUpdateSchedule(scheduleIndex, { timezone: event.target.value })}
          data-testid="settings-integrator-schedule-timezone"
        />
        <datalist id="integrator-schedule-timezones">
          {COMMON_TIMEZONES.map((timezone) => (
            <option key={timezone} value={timezone} />
          ))}
        </datalist>
      </label>
      <div className="rounded-lg border border-bg-border bg-bg-tertiary/30 px-3 py-2 text-[11px] text-text-secondary">
        Manual trigger:{' '}
        <b className="text-text-primary">
          {scheduleRuntime?.manual_trigger_supported === false ? 'Unsupported' : 'Supported'}
        </b>
      </div>
    </div>

    <label className="inline-flex items-center gap-2 text-xs text-text-secondary">
      <input
        type="checkbox"
        checked={schedule.enabled}
        onChange={(event) => onUpdateSchedule(scheduleIndex, { enabled: event.target.checked })}
        data-testid="settings-integrator-schedule-enabled"
      />
      Enabled
    </label>
  </>
)
