import {
  DASHBOARD_CHART_OPTIONS,
  type DashboardChartType,
} from './dashboardTemplateModel'
import { PromptDashboardTemplateFieldLabel } from './PromptDashboardTemplateFieldLabel'
import type { PromptDashboardTemplateEnabledProps } from './PromptDashboardTemplateFieldTypes'

const CHART_LABELS: Record<DashboardChartType, string> = {
  bar: '柱状图',
  line: '折线图',
  pie: '饼图',
}

interface PromptDashboardTemplateChartsFieldProps
  extends PromptDashboardTemplateEnabledProps {
  preferredCharts: DashboardChartType[]
  onToggleChart: (chartType: DashboardChartType) => void
}

export function PromptDashboardTemplateChartsField({
  enabled,
  preferredCharts,
  onToggleChart,
}: PromptDashboardTemplateChartsFieldProps) {
  return (
    <div>
      <PromptDashboardTemplateFieldLabel>
        偏好图表
      </PromptDashboardTemplateFieldLabel>
      <div className="flex flex-wrap gap-2">
        {DASHBOARD_CHART_OPTIONS.map((value) => {
          const checked = preferredCharts.includes(value)
          const label = CHART_LABELS[value]

          return (
            <button
              key={value}
              type="button"
              data-testid={`settings-prompt-dashboard-chart-${value}`}
              onClick={() => onToggleChart(value)}
              disabled={!enabled}
              className={`px-2.5 py-1 rounded-lg text-[11px] border transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                checked
                  ? 'border-accent-blue/50 bg-accent-blue/15 text-accent-blue'
                  : 'border-bg-border text-text-secondary hover:text-text-primary'
              }`}
            >
              {label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
