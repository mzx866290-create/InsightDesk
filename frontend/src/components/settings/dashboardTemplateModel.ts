import type { DashboardTemplateConfig } from '../../api/client'

export type DashboardChartType = DashboardTemplateConfig['preferred_charts'][number]
export type DashboardSectionType = DashboardTemplateConfig['section_order'][number]

export const DASHBOARD_CHART_OPTIONS: DashboardChartType[] = ['bar', 'line', 'pie']

export const DASHBOARD_SECTION_ORDER_OPTIONS: DashboardSectionType[] = [
  'summary',
  'metrics',
  'charts',
  'table',
  'evidence',
  'warnings',
]

export const DEFAULT_DASHBOARD_TEMPLATE: DashboardTemplateConfig = {
  enabled: true,
  title_hint: '知识看板',
  focus_metrics: [],
  preferred_charts: ['bar', 'line', 'pie'],
  section_order: DASHBOARD_SECTION_ORDER_OPTIONS,
  audience_tone: '专业、直观、适合业务汇报',
}

export function normalizeDashboardTemplate(
  template?: Partial<DashboardTemplateConfig> | null,
): DashboardTemplateConfig {
  const preferredCharts = Array.isArray(template?.preferred_charts)
    ? template.preferred_charts.filter((item): item is DashboardChartType =>
        DASHBOARD_CHART_OPTIONS.includes(item as DashboardChartType),
      )
    : DEFAULT_DASHBOARD_TEMPLATE.preferred_charts

  const sectionOrder = Array.isArray(template?.section_order)
    ? template.section_order.filter((item): item is DashboardSectionType =>
        DASHBOARD_SECTION_ORDER_OPTIONS.includes(item as DashboardSectionType),
      )
    : DEFAULT_DASHBOARD_TEMPLATE.section_order

  return {
    enabled: template?.enabled !== false,
    title_hint: template?.title_hint?.trim() || DEFAULT_DASHBOARD_TEMPLATE.title_hint,
    focus_metrics: Array.isArray(template?.focus_metrics)
      ? template.focus_metrics.filter(Boolean)
      : DEFAULT_DASHBOARD_TEMPLATE.focus_metrics,
    preferred_charts: preferredCharts.length > 0
      ? preferredCharts
      : DEFAULT_DASHBOARD_TEMPLATE.preferred_charts,
    section_order: sectionOrder.length > 0
      ? sectionOrder
      : DEFAULT_DASHBOARD_TEMPLATE.section_order,
    audience_tone: template?.audience_tone?.trim() || DEFAULT_DASHBOARD_TEMPLATE.audience_tone,
  }
}
