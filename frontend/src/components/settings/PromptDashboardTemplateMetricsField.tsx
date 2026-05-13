import { PromptDashboardTemplateFieldLabel } from './PromptDashboardTemplateFieldLabel'
import type { PromptDashboardTemplateEnabledProps } from './PromptDashboardTemplateFieldTypes'

interface PromptDashboardTemplateMetricsFieldProps
  extends PromptDashboardTemplateEnabledProps {
  focusMetrics: string
  onFocusMetricsChange: (value: string) => void
}

export function PromptDashboardTemplateMetricsField({
  enabled,
  focusMetrics,
  onFocusMetricsChange,
}: PromptDashboardTemplateMetricsFieldProps) {
  return (
    <div>
      <PromptDashboardTemplateFieldLabel hint="（每行一个）">
        关注指标
      </PromptDashboardTemplateFieldLabel>
      <textarea
        data-testid="settings-prompt-dashboard-focus-metrics"
        className="input-base w-full text-sm resize-none leading-relaxed"
        rows={4}
        placeholder={'例如：\n销售额\n客户数\n渠道占比'}
        value={focusMetrics}
        onChange={(event) => onFocusMetricsChange(event.target.value)}
        disabled={!enabled}
      />
    </div>
  )
}
