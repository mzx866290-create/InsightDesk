import React from 'react';
import { Search, X } from 'lucide-react';

import type { TraceEventKind } from '../../api/client';
import { useI18n } from '../../i18n';
import { Button } from '../ui/Button';

export interface TraceOperationsFiltersProps {
  eventFilter: TraceEventKind | '';
  nameFilter: string;
  traceIdFilter: string;
  spanIdFilter: string;
  loading: boolean;
  canResetFilters: boolean;
  onEventFilterChange: (value: TraceEventKind | '') => void;
  onNameFilterChange: (value: string) => void;
  onTraceIdFilterChange: (value: string) => void;
  onSpanIdFilterChange: (value: string) => void;
  onApplyFilters: () => void;
  onResetFilters: () => void;
}

export const TraceOperationsFilters: React.FC<TraceOperationsFiltersProps> = ({
  eventFilter,
  nameFilter,
  traceIdFilter,
  spanIdFilter,
  loading,
  canResetFilters,
  onEventFilterChange,
  onNameFilterChange,
  onTraceIdFilterChange,
  onSpanIdFilterChange,
  onApplyFilters,
  onResetFilters,
}) => {
  const { t } = useI18n();

  const handleInputKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      onApplyFilters();
    }
  };

  return (
    <div className="grid gap-2 rounded-lg border border-bg-border bg-bg-tertiary/30 p-3 text-xs text-text-secondary md:grid-cols-[8rem_minmax(9rem,1fr)_minmax(10rem,1fr)_minmax(10rem,1fr)_auto]">
      <select
        className="input-base min-h-11 py-2 text-xs"
        value={eventFilter}
        onChange={(event) => onEventFilterChange(event.target.value as TraceEventKind | '')}
        aria-label={t('settings.traces.allEvents')}
        data-testid="settings-trace-filter-event"
      >
        <option value="">{t('settings.traces.allEvents')}</option>
        <option value="start">start</option>
        <option value="end">end</option>
        <option value="error">error</option>
      </select>
      <input
        className="input-base min-h-11 py-2 text-xs"
        placeholder={t('settings.traces.spanName')}
        value={nameFilter}
        onChange={(event) => onNameFilterChange(event.target.value)}
        onKeyDown={handleInputKeyDown}
        data-testid="settings-trace-filter-name"
      />
      <input
        className="input-base min-h-11 py-2 font-mono text-xs"
        placeholder={t('settings.traces.traceId')}
        value={traceIdFilter}
        onChange={(event) => onTraceIdFilterChange(event.target.value)}
        onKeyDown={handleInputKeyDown}
        data-testid="settings-trace-filter-trace-id"
      />
      <input
        className="input-base min-h-11 py-2 font-mono text-xs"
        placeholder={t('settings.traces.spanId')}
        value={spanIdFilter}
        onChange={(event) => onSpanIdFilterChange(event.target.value)}
        onKeyDown={handleInputKeyDown}
        data-testid="settings-trace-filter-span-id"
      />
      <div className="flex items-center gap-2">
        <Button
          variant="primary"
          size="sm"
          onClick={onApplyFilters}
          loading={loading}
          className="min-h-11"
          data-testid="settings-trace-apply-filters"
        >
          <Search size={12} />
          {t('settings.traces.applyFilters')}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={onResetFilters}
          disabled={!canResetFilters}
          className="min-h-11"
          data-testid="settings-trace-reset-filters"
        >
          <X size={12} />
          {t('settings.traces.resetFilters')}
        </Button>
      </div>
    </div>
  );
};
