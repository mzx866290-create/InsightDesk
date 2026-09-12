import React from 'react';
import { BarChart3, FileJson } from 'lucide-react';
import type { TraceDashboardCard, TraceExportPreview, TracePanelTemplate } from '../../api/client';
import { useI18n, type TranslationKey } from '../../i18n';
import { formatDuration, formatNodeSummary } from './traceOperationsModel';

const CARD_TITLE_KEYS: Record<string, TranslationKey> = {
  trace_events: 'settings.traces.cardTraceEvents',
  export_spans: 'settings.traces.cardOtlpSpans',
  trace_errors: 'settings.traces.cardTraceErrors',
  process_nodes: 'settings.traces.cardProcessNodes',
};

const CARD_UNIT_KEYS: Record<string, TranslationKey> = {
  events: 'settings.traces.unitEvents',
  spans: 'settings.traces.unitSpans',
  errors: 'settings.traces.unitErrors',
  nodes: 'settings.traces.unitNodes',
};

const TEMPLATE_TITLE_KEYS: Record<string, TranslationKey> = {
  trace_export_preview: 'settings.traces.templateExportPreview',
  trace_process_aggregation: 'settings.traces.templateProcessAggregation',
};

interface TraceDashboardPreviewProps {
  dashboardCards: TraceDashboardCard[];
  exportPreview: TraceExportPreview | null;
  panelTemplates: TracePanelTemplate[];
}

export const TraceDashboardPreview: React.FC<TraceDashboardPreviewProps> = ({
  dashboardCards,
  exportPreview,
  panelTemplates,
}) => {
  const { t } = useI18n();

  if (dashboardCards.length === 0 && !exportPreview) return null;

  const templateTitles = panelTemplates.map((template) => {
    const titleKey = TEMPLATE_TITLE_KEYS[template.id];
    return titleKey ? t(titleKey) : template.title;
  });

  return (
    <div
      className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.8fr)]"
      data-testid="settings-trace-dashboard-preview"
    >
      <div className="rounded-lg border border-bg-border bg-bg-tertiary/30 p-3">
        <div className="mb-2 flex items-center gap-2 text-xs font-medium text-text-primary">
          <BarChart3 size={13} className="text-accent-blue" />
          {t('settings.traces.dashboardCards')}
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          {dashboardCards.map((card) => {
            const titleKey = CARD_TITLE_KEYS[card.id];
            const unitKey = card.unit ? CARD_UNIT_KEYS[card.unit] : undefined;

            return (
              <div
                key={card.id}
                className="rounded border border-bg-border bg-bg-primary/40 px-3 py-2"
              >
                <p className="truncate text-[11px] text-text-secondary">
                  {titleKey ? t(titleKey) : card.title}
                </p>
                <p
                  className={
                    card.severity === 'warning' || card.severity === 'error'
                      ? 'mt-1 font-mono text-sm text-accent-red'
                      : 'mt-1 font-mono text-sm text-text-primary'
                  }
                >
                  {card.value}
                  {card.unit ? (
                    <span className="ml-1 text-[10px] text-text-secondary">
                      {unitKey ? t(unitKey) : card.unit}
                    </span>
                  ) : null}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      <div className="rounded-lg border border-bg-border bg-bg-tertiary/30 p-3">
        <div className="mb-2 flex items-center gap-2 text-xs font-medium text-text-primary">
          <FileJson size={13} className="text-accent-green" />
          {t('settings.traces.exportPreview')}
        </div>
        <div className="space-y-1.5 text-xs text-text-secondary">
          <p>
            {t('settings.traces.serviceName')}：
            <b className="text-text-primary">{exportPreview?.service_name ?? '-'}</b>
          </p>
          <p>
            {t('settings.traces.spansLogs')}：
            <b className="text-text-primary">{exportPreview?.span_count ?? 0}</b> /{' '}
            {exportPreview?.log_record_count ?? 0}
          </p>
          <p>
            {t('settings.traces.sources')}：
            <b className="text-text-primary">{formatNodeSummary(exportPreview?.source_nodes)}</b>
          </p>
          <p>
            {t('settings.traces.processes')}：
            <b className="text-text-primary">{formatNodeSummary(exportPreview?.process_nodes)}</b>
          </p>
          <p>
            {t('settings.traces.averageDuration')}：
            <b className="text-text-primary">
              {formatDuration(exportPreview?.avg_duration_ms ?? null)}
            </b>
          </p>
          {panelTemplates.length > 0 && (
            <p className="truncate" title={templateTitles.join(' | ')}>
              {t('settings.traces.templates')}：
              <b className="text-text-primary">
                {panelTemplates.map((template) => template.id).join(' | ')}
              </b>
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
