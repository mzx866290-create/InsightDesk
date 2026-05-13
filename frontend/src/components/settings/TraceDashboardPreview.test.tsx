import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { TraceDashboardCard, TraceExportPreview, TracePanelTemplate } from '../../api/client'
import { TraceDashboardPreview } from './TraceDashboardPreview'

const card = (patch: Partial<TraceDashboardCard>): TraceDashboardCard => ({
  id: 'card-1',
  title: 'Total spans',
  value: 123,
  ...patch,
})

const exportPreview = (patch: Partial<TraceExportPreview> = {}): TraceExportPreview => ({
  service_name: 'insightdesk',
  span_count: 8,
  log_record_count: 2,
  source_nodes: { api: 3, worker: 2 },
  process_nodes: { web: 4 },
  avg_duration_ms: 12.3,
  sample_spans: [],
  ...patch,
})

const template = (patch: Partial<TracePanelTemplate> = {}): TracePanelTemplate => ({
  id: 'trace-spans',
  title: 'Trace spans panel',
  kind: 'stat',
  source: 'trace',
  fields: [],
  ...patch,
})

describe('TraceDashboardPreview', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders nothing when both sections are empty', () => {
    const { container } = render(
      <TraceDashboardPreview dashboardCards={[]} exportPreview={null} panelTemplates={[]} />,
    )

    expect(container.firstChild).toBeNull()
  })

  it('renders cards and export preview', () => {
    render(
      <TraceDashboardPreview
        dashboardCards={[card({ severity: 'error', unit: 'events' })]}
        exportPreview={exportPreview()}
        panelTemplates={[template(), template({ id: 'logs', title: 'Trace logs panel' })]}
      />,
    )

    expect(screen.getByTestId('settings-trace-dashboard-preview')).toBeInTheDocument()
    expect(screen.getByText('Total spans')).toBeInTheDocument()
    expect(screen.getByText('123')).toBeInTheDocument()
    expect(screen.getByText('events')).toBeInTheDocument()
    expect(screen.getByText('insightdesk')).toBeInTheDocument()
    expect(
      within(screen.getByTestId('settings-trace-dashboard-preview')).getByText(
        (_, element) => element?.tagName === 'P' && element.textContent === 'spans/logs：8 / 2',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('api:3 | worker:2')).toBeInTheDocument()
    expect(screen.getByText('web:4')).toBeInTheDocument()
    expect(within(screen.getByTestId('settings-trace-dashboard-preview')).getByTitle('Trace spans panel | Trace logs panel')).toBeInTheDocument()
  })
})
