import React from 'react'

import type { ConnectorDraft } from './integratorConnectorModel'
import type { ScheduleDraft, ScheduleRuntime } from './integratorScheduleModel'
import { IntegratorScheduleDetailsHeader } from './IntegratorScheduleDetailsHeader'
import { IntegratorScheduleFormFields } from './IntegratorScheduleFormFields'
import { IntegratorScheduleRunSummary } from './IntegratorScheduleRunSummary'

export interface IntegratorScheduleDetailsPanelProps {
  selectedSchedule: ScheduleDraft | null
  selectedScheduleIndex: number
  connectors: ConnectorDraft[]
  scheduleRuntime: ScheduleRuntime | null
  scheduleLoading: boolean
  triggeringScheduleId: string | null
  onRemoveSchedule: (index: number) => void
  onUpdateSchedule: (index: number, patch: Partial<ScheduleDraft>) => void
  onTriggerSchedule: (schedule: ScheduleDraft) => void
}

export const IntegratorScheduleDetailsPanel: React.FC<IntegratorScheduleDetailsPanelProps> = ({
  selectedSchedule,
  selectedScheduleIndex,
  connectors,
  scheduleRuntime,
  scheduleLoading,
  triggeringScheduleId,
  onRemoveSchedule,
  onUpdateSchedule,
  onTriggerSchedule,
}) => (
  <div className="rounded-lg border border-bg-border bg-bg-secondary/30 p-3">
    {selectedSchedule ? (
      <div className="space-y-3">
        <IntegratorScheduleDetailsHeader
          selectedSchedule={selectedSchedule}
          selectedScheduleIndex={selectedScheduleIndex}
          triggeringScheduleId={triggeringScheduleId}
          onRemoveSchedule={onRemoveSchedule}
          onTriggerSchedule={onTriggerSchedule}
        />

        <IntegratorScheduleFormFields
          connectors={connectors}
          schedule={selectedSchedule}
          scheduleIndex={selectedScheduleIndex}
          scheduleRuntime={scheduleRuntime}
          onUpdateSchedule={onUpdateSchedule}
        />

        <IntegratorScheduleRunSummary schedule={selectedSchedule} />
      </div>
    ) : (
      <div className="flex min-h-[12rem] items-center justify-center text-xs text-text-secondary">
        {scheduleLoading ? 'Loading schedules...' : 'No schedule selected'}
      </div>
    )}
  </div>
)
