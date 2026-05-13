import React from 'react'

import type { IntegratorScheduleTickResponse } from '../../api/client'
import type { ConnectorDraft } from './integratorConnectorModel'
import type { ScheduleDraft, ScheduleRuntime } from './integratorScheduleModel'
import { IntegratorScheduleDetailsPanel } from './IntegratorScheduleDetailsPanel'
import { IntegratorScheduleListPanel } from './IntegratorScheduleListPanel'
import { IntegratorSchedulesHeaderPanel } from './IntegratorSchedulesHeaderPanel'

export interface IntegratorSchedulesPanelProps {
  schedules: ScheduleDraft[]
  selectedScheduleIndex: number
  selectedSchedule: ScheduleDraft | null
  connectors: ConnectorDraft[]
  scheduleRuntime: ScheduleRuntime | null
  scheduleTickResult: IntegratorScheduleTickResponse | null
  scheduleValidationErrors: string[]
  scheduleNotice: string | null
  scheduleError: string | null
  scheduleLoading: boolean
  scheduleSaving: boolean
  scheduleTicking: boolean
  triggeringScheduleId: string | null
  onRefreshSchedules: () => void
  onDryRunScheduleTick: () => void
  onAddSchedule: () => void
  onSaveSchedules: () => void
  onSelectSchedule: (index: number) => void
  onRemoveSchedule: (index: number) => void
  onUpdateSchedule: (index: number, patch: Partial<ScheduleDraft>) => void
  onTriggerSchedule: (schedule: ScheduleDraft) => void
}

export const IntegratorSchedulesPanel: React.FC<IntegratorSchedulesPanelProps> = ({
  schedules,
  selectedScheduleIndex,
  selectedSchedule,
  connectors,
  scheduleRuntime,
  scheduleTickResult,
  scheduleValidationErrors,
  scheduleNotice,
  scheduleError,
  scheduleLoading,
  scheduleSaving,
  scheduleTicking,
  triggeringScheduleId,
  onRefreshSchedules,
  onDryRunScheduleTick,
  onAddSchedule,
  onSaveSchedules,
  onSelectSchedule,
  onRemoveSchedule,
  onUpdateSchedule,
  onTriggerSchedule,
}) => {
  return (
    <div
      className="rounded-lg border border-bg-border bg-bg-tertiary/20 p-3"
      data-testid="settings-integrator-schedules-panel"
    >
      <IntegratorSchedulesHeaderPanel
        scheduleCount={schedules.length}
        scheduleRuntime={scheduleRuntime}
        scheduleTickResult={scheduleTickResult}
        scheduleValidationErrors={scheduleValidationErrors}
        scheduleNotice={scheduleNotice}
        scheduleError={scheduleError}
        scheduleLoading={scheduleLoading}
        scheduleSaving={scheduleSaving}
        scheduleTicking={scheduleTicking}
        onRefreshSchedules={onRefreshSchedules}
        onDryRunScheduleTick={onDryRunScheduleTick}
        onAddSchedule={onAddSchedule}
        onSaveSchedules={onSaveSchedules}
      />

      <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.35fr)]">
        <IntegratorScheduleListPanel
          schedules={schedules}
          selectedScheduleIndex={selectedScheduleIndex}
          scheduleError={scheduleError}
          scheduleLoading={scheduleLoading}
          onAddSchedule={onAddSchedule}
          onSelectSchedule={onSelectSchedule}
        />

        <IntegratorScheduleDetailsPanel
          selectedSchedule={selectedSchedule}
          selectedScheduleIndex={selectedScheduleIndex}
          connectors={connectors}
          scheduleRuntime={scheduleRuntime}
          scheduleLoading={scheduleLoading}
          triggeringScheduleId={triggeringScheduleId}
          onRemoveSchedule={onRemoveSchedule}
          onUpdateSchedule={onUpdateSchedule}
          onTriggerSchedule={onTriggerSchedule}
        />
      </div>
    </div>
  )
}
