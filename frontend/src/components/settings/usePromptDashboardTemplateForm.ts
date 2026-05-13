import { useCallback, useMemo, useState } from 'react'
import type { DashboardTemplateConfig } from '../../api/client'
import {
  DASHBOARD_SECTION_ORDER_OPTIONS,
  type DashboardChartType,
  normalizeDashboardTemplate,
} from './dashboardTemplateModel'

interface PromptDashboardTemplateForm {
  enabled: boolean
  titleHint: string
  audienceTone: string
  focusMetrics: string
  sectionOrder: string
  preferredCharts: DashboardChartType[]
}

function templateToForm(template?: Partial<DashboardTemplateConfig> | null): PromptDashboardTemplateForm {
  const normalized = normalizeDashboardTemplate(template)
  return {
    enabled: normalized.enabled,
    titleHint: normalized.title_hint,
    audienceTone: normalized.audience_tone,
    focusMetrics: normalized.focus_metrics.join('\n'),
    sectionOrder: normalized.section_order.join('\n'),
    preferredCharts: normalized.preferred_charts,
  }
}

export function usePromptDashboardTemplateForm() {
  const defaultForm = templateToForm()
  const [enabled, setEnabled] = useState(defaultForm.enabled)
  const [titleHint, setTitleHint] = useState(defaultForm.titleHint)
  const [audienceTone, setAudienceTone] = useState(defaultForm.audienceTone)
  const [focusMetrics, setFocusMetrics] = useState(defaultForm.focusMetrics)
  const [sectionOrder, setSectionOrder] = useState(defaultForm.sectionOrder)
  const [preferredCharts, setPreferredCharts] = useState<DashboardChartType[]>(defaultForm.preferredCharts)

  const applyForm = (form: PromptDashboardTemplateForm) => {
    setEnabled(form.enabled)
    setTitleHint(form.titleHint)
    setAudienceTone(form.audienceTone)
    setFocusMetrics(form.focusMetrics)
    setSectionOrder(form.sectionOrder)
    setPreferredCharts(form.preferredCharts)
  }

  const loadFromTemplate = (template?: Partial<DashboardTemplateConfig> | null) => {
    applyForm(templateToForm(template))
  }

  const reset = () => {
    applyForm(templateToForm())
  }

  const buildPayload = (): DashboardTemplateConfig => {
    const focusMetricItems = focusMetrics
      .split('\n')
      .map((item) => item.trim())
      .filter(Boolean)

    const sectionOrderItems = sectionOrder
      .split('\n')
      .map((item) => item.trim())
      .filter((item): item is DashboardTemplateConfig['section_order'][number] =>
        DASHBOARD_SECTION_ORDER_OPTIONS.includes(item as DashboardTemplateConfig['section_order'][number]),
      )

    return normalizeDashboardTemplate({
      enabled,
      title_hint: titleHint,
      audience_tone: audienceTone,
      focus_metrics: focusMetricItems,
      preferred_charts: preferredCharts,
      section_order: sectionOrderItems,
    })
  }

  const toggleEnabled = useCallback(() => {
    setEnabled((current) => !current)
  }, [])

  const toggleChart = useCallback((chartType: DashboardChartType) => {
    setPreferredCharts((current) => {
      if (current.includes(chartType)) {
        // Keep one chart selected so the normalized payload never falls back unexpectedly.
        return current.length > 1 ? current.filter((item) => item !== chartType) : current
      }

      return [...current, chartType]
    })
  }, [])

  const fieldsProps = useMemo(() => ({
    enabled,
    titleHint,
    audienceTone,
    focusMetrics,
    sectionOrder,
    preferredCharts,
    onEnabledChange: toggleEnabled,
    onTitleHintChange: setTitleHint,
    onAudienceToneChange: setAudienceTone,
    onFocusMetricsChange: setFocusMetrics,
    onSectionOrderChange: setSectionOrder,
    onToggleChart: toggleChart,
  }), [
    enabled,
    titleHint,
    audienceTone,
    focusMetrics,
    sectionOrder,
    preferredCharts,
    toggleEnabled,
    toggleChart,
  ])

  return {
    enabled,
    titleHint,
    audienceTone,
    focusMetrics,
    sectionOrder,
    preferredCharts,
    fieldsProps,
    loadFromTemplate,
    reset,
    buildPayload,
  }
}
