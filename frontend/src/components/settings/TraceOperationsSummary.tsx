import React from 'react';

import type { TraceSummary } from '../../api/client';
import { useI18n } from '../../i18n';

interface TraceOperationsSummaryProps {
  filtersActive: boolean;
  latestTimestamp: string;
  summary: TraceSummary;
}

export const TraceOperationsSummary: React.FC<TraceOperationsSummaryProps> = ({
  filtersActive,
  latestTimestamp,
  summary,
}) => {
  const { t } = useI18n();

  return (
    <div
      className="grid gap-2 rounded-lg border border-bg-border bg-bg-tertiary/30 px-3 py-2 text-xs text-text-secondary sm:grid-cols-4"
      data-testid="settings-trace-summary"
    >
      <span>
        {t('settings.traces.returned')}：<b className="text-text-primary">{summary.returned}</b> /{' '}
        {summary.limit}
      </span>
      <span>
        {t('settings.traces.errors')}：<b className="text-accent-red">{summary.error_events}</b>
      </span>
      <span>
        {t('settings.traces.latestEvent')}：<b className="text-text-primary">{latestTimestamp}</b>
      </span>
      <span>
        {t('settings.traces.filterStatus')}：
        <b className="text-text-primary" data-testid="settings-trace-filter-status">
          {filtersActive ? t('settings.traces.filtered') : t('settings.traces.all')}
        </b>
      </span>
    </div>
  );
};
