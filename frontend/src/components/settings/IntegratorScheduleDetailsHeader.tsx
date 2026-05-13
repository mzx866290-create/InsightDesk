import React from 'react'
import { Play, Trash2 } from 'lucide-react'

import type { ScheduleDraft } from './integratorScheduleModel'
import { Button } from '../ui/Button'

interface IntegratorScheduleDetailsHeaderProps {
  selectedSchedule: ScheduleDraft
  selectedScheduleIndex: number
  triggeringScheduleId: string | null
  onRemoveSchedule: (index: number) => void
  onTriggerSchedule: (schedule: ScheduleDraft) => void
}

export const IntegratorScheduleDetailsHeader: React.FC<IntegratorScheduleDetailsHeaderProps> = ({
  selectedSchedule,
  selectedScheduleIndex,
  triggeringScheduleId,
  onRemoveSchedule,
  onTriggerSchedule,
}) => (
  <div className="flex items-start justify-between gap-3">
    <div>
      <h5 className="text-sm font-medium text-text-primary">Schedule details</h5>
      <p className="mt-1 text-xs text-text-secondary">
        Settings are preserved by the API and are not rendered here.
      </p>
    </div>
    <div className="flex flex-wrap gap-2">
      <Button
        variant="outline"
        size="sm"
        onClick={() => onTriggerSchedule(selectedSchedule)}
        loading={triggeringScheduleId === selectedSchedule.schedule_id}
        data-testid="settings-integrator-schedule-trigger"
      >
        <Play size={12} />
        Trigger
      </Button>
      <Button
        variant="danger"
        size="sm"
        onClick={() => onRemoveSchedule(selectedScheduleIndex)}
        data-testid="settings-integrator-schedule-remove"
      >
        <Trash2 size={12} />
        Remove
      </Button>
    </div>
  </div>
)
