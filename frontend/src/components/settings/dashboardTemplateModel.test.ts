import { describe, expect, it } from 'vitest'

import {
  DASHBOARD_SECTION_ORDER_OPTIONS,
  DEFAULT_DASHBOARD_TEMPLATE,
  normalizeDashboardTemplate,
} from './dashboardTemplateModel'

describe('dashboardTemplateModel', () => {
  it('returns defaults when template is missing', () => {
    expect(normalizeDashboardTemplate(null)).toEqual(DEFAULT_DASHBOARD_TEMPLATE)
  })

  it('trims text fields and keeps explicit disabled state', () => {
    expect(
      normalizeDashboardTemplate({
        enabled: false,
        title_hint: '  Revenue health  ',
        audience_tone: '  concise executive summary  ',
        focus_metrics: ['MRR', '', 'churn'],
      }),
    ).toMatchObject({
      enabled: false,
      title_hint: 'Revenue health',
      audience_tone: 'concise executive summary',
      focus_metrics: ['MRR', 'churn'],
    })
  })

  it('filters unsupported charts and section keys before falling back to defaults', () => {
    expect(
      normalizeDashboardTemplate({
        preferred_charts: ['line', 'scatter', 'pie'] as never,
        section_order: ['metrics', 'unknown', 'warnings'] as never,
      }),
    ).toMatchObject({
      preferred_charts: ['line', 'pie'],
      section_order: ['metrics', 'warnings'],
    })

    expect(
      normalizeDashboardTemplate({
        preferred_charts: ['scatter'] as never,
        section_order: ['unknown'] as never,
      }),
    ).toMatchObject({
      preferred_charts: DEFAULT_DASHBOARD_TEMPLATE.preferred_charts,
      section_order: DASHBOARD_SECTION_ORDER_OPTIONS,
    })
  })
})
