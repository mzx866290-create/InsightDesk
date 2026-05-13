import { PromptDashboardTemplateFieldLabel } from './PromptDashboardTemplateFieldLabel'
import type { PromptDashboardTemplateEnabledProps } from './PromptDashboardTemplateFieldTypes'

interface PromptDashboardTemplateSectionsFieldProps
  extends PromptDashboardTemplateEnabledProps {
  sectionOrder: string
  onSectionOrderChange: (value: string) => void
}

export function PromptDashboardTemplateSectionsField({
  enabled,
  sectionOrder,
  onSectionOrderChange,
}: PromptDashboardTemplateSectionsFieldProps) {
  return (
    <div>
      <PromptDashboardTemplateFieldLabel hint="（每行一个部分）">
        展示顺序
      </PromptDashboardTemplateFieldLabel>
      <textarea
        data-testid="settings-prompt-dashboard-section-order"
        className="input-base w-full text-sm resize-none leading-relaxed"
        rows={6}
        value={sectionOrder}
        onChange={(event) => onSectionOrderChange(event.target.value)}
        placeholder={'summary\nmetrics\ncharts\ntable\nevidence\nwarnings'}
        disabled={!enabled}
      />
      <p className="mt-1 text-[11px] text-text-secondary/55">
        可用值：summary、metrics、charts、table、evidence、warnings
      </p>
    </div>
  )
}
