import React from 'react'

import { formatAuditTime } from './integratorAuditModel'
import { normalizeScheduleTimezone, type ScheduleDraft } from './integratorScheduleModel'

interface IntegratorScheduleRunSummaryProps {
  schedule: ScheduleDraft
}

export const IntegratorScheduleRunSummary: React.FC<IntegratorScheduleRunSummaryProps> = ({
  schedule,
}) => (
  <div className="grid gap-2 rounded-lg border border-bg-border bg-bg-tertiary/30 px-3 py-2 text-[11px] text-text-secondary sm:grid-cols-2">
    <span>
      Last run: <b className="text-text-primary">{formatAuditTime(schedule.last_run_at ?? 0)}</b>
    </span>
    <span>
      Next run: <b className="text-text-primary">{formatAuditTime(schedule.next_run_at ?? 0)}</b>
    </span>
    <span>
      Timezone:{' '}
      <b className="text-text-primary" data-testid="settings-integrator-schedule-timezone-display">
        {normalizeScheduleTimezone(schedule.timezone)}
      </b>
    </span>
  </div>
)
