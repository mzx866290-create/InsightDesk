import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import type { TraceDashboardCard, TraceExportPreview, TracePanelTemplate } from '../../api/client';
import { translations } from '../../i18n';
import { useChatStore } from '../../stores/chatStore';
import { TraceDashboardPreview } from './TraceDashboardPreview';

const card = (patch: Partial<TraceDashboardCard>): TraceDashboardCard => ({
  id: 'card-1',
  title: 'Total spans',
  value: 123,
  ...patch,
});

const exportPreview = (patch: Partial<TraceExportPreview> = {}): TraceExportPreview => ({
  service_name: 'insightdesk',
  span_count: 8,
  log_record_count: 2,
  source_nodes: { api: 3, worker: 2 },
  process_nodes: { web: 4 },
  avg_duration_ms: 12.3,
  sample_spans: [],
  ...patch,
});

const template = (patch: Partial<TracePanelTemplate> = {}): TracePanelTemplate => ({
  id: 'trace-spans',
  title: 'Trace spans panel',
  kind: 'stat',
  source: 'trace',
  fields: [],
  ...patch,
});

describe('TraceDashboardPreview', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders nothing when both sections are empty', () => {
    const { container } = render(
      <TraceDashboardPreview dashboardCards={[]} exportPreview={null} panelTemplates={[]} />
    );

    expect(container.firstChild).toBeNull();
  });

  it('renders cards and export preview', () => {
    useChatStore.setState({ language: 'zh-CN' });
    const zh = translations['zh-CN'];

    render(
      <TraceDashboardPreview
        dashboardCards={[
          card({ id: 'trace_events', title: 'Trace events', severity: 'error', unit: 'events' }),
          card({ id: 'export_spans', title: 'OTLP spans', value: 8, unit: 'spans' }),
          card({ id: 'trace_errors', title: 'Trace errors', value: 2, unit: 'errors' }),
          card({ id: 'process_nodes', title: 'Process nodes', value: 1, unit: 'nodes' }),
        ]}
        exportPreview={exportPreview()}
        panelTemplates={[template(), template({ id: 'logs', title: 'Trace logs panel' })]}
      />
    );

    expect(screen.getByTestId('settings-trace-dashboard-preview')).toBeInTheDocument();
    expect(screen.getByText(zh['settings.traces.dashboardCards'])).toBeInTheDocument();
    expect(screen.getByText(zh['settings.traces.cardTraceEvents'])).toBeInTheDocument();
    expect(screen.getByText(zh['settings.traces.cardOtlpSpans'])).toBeInTheDocument();
    expect(screen.getByText(zh['settings.traces.cardTraceErrors'])).toBeInTheDocument();
    expect(screen.getByText(zh['settings.traces.cardProcessNodes'])).toBeInTheDocument();
    expect(screen.getByText('123')).toBeInTheDocument();
    expect(screen.getByText(zh['settings.traces.unitEvents'])).toBeInTheDocument();
    expect(screen.getByText(zh['settings.traces.unitSpans'])).toBeInTheDocument();
    expect(screen.getByText(zh['settings.traces.unitErrors'])).toBeInTheDocument();
    expect(screen.getByText(zh['settings.traces.unitNodes'])).toBeInTheDocument();
    expect(screen.getByText(zh['settings.traces.exportPreview'])).toBeInTheDocument();
    expect(screen.getByText('insightdesk')).toBeInTheDocument();
    expect(
      within(screen.getByTestId('settings-trace-dashboard-preview')).getByText(
        (_, element) =>
          element?.tagName === 'P' &&
          element.textContent === `${zh['settings.traces.spansLogs']}：8 / 2`
      )
    ).toBeInTheDocument();
    expect(screen.getByText('api:3 | worker:2')).toBeInTheDocument();
    expect(screen.getByText('web:4')).toBeInTheDocument();
    expect(
      within(screen.getByTestId('settings-trace-dashboard-preview')).getByTitle(
        'Trace spans panel | Trace logs panel'
      )
    ).toBeInTheDocument();
  });
});
