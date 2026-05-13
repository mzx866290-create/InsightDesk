import React from 'react'
import {
  PromptDashboardTemplateChartsField,
  PromptDashboardTemplateMetricsField,
  PromptDashboardTemplateSectionsField,
  PromptDashboardTemplateTextFields,
  PromptDashboardTemplateToggleCard,
} from './PromptDashboardTemplateFieldGroups'
import type { DashboardChartType } from './dashboardTemplateModel'

export interface PromptDashboardTemplateFieldsProps {
  enabled: boolean
  titleHint: string
  audienceTone: string
  focusMetrics: string
  sectionOrder: string
  preferredCharts: DashboardChartType[]
  onEnabledChange: () => void
  onTitleHintChange: (value: string) => void
  onAudienceToneChange: (value: string) => void
  onFocusMetricsChange: (value: string) => void
  onSectionOrderChange: (value: string) => void
  onToggleChart: (chartType: DashboardChartType) => void
}

export const PromptDashboardTemplateFields: React.FC<PromptDashboardTemplateFieldsProps> = ({
  enabled,
  titleHint,
  audienceTone,
  focusMetrics,
  sectionOrder,
  preferredCharts,
  onEnabledChange,
  onTitleHintChange,
  onAudienceToneChange,
  onFocusMetricsChange,
  onSectionOrderChange,
  onToggleChart,
}) => (
  <div className="rounded-lg border border-bg-border bg-bg-primary/30 p-3 space-y-3 lg:row-span-3">
    <PromptDashboardTemplateToggleCard
      enabled={enabled}
      onEnabledChange={onEnabledChange}
    />

    <div className={`space-y-3 ${enabled ? '' : 'opacity-55'}`}>
      <PromptDashboardTemplateTextFields
        enabled={enabled}
        titleHint={titleHint}
        audienceTone={audienceTone}
        onTitleHintChange={onTitleHintChange}
        onAudienceToneChange={onAudienceToneChange}
      />
      <PromptDashboardTemplateMetricsField
        enabled={enabled}
        focusMetrics={focusMetrics}
        onFocusMetricsChange={onFocusMetricsChange}
      />
      <PromptDashboardTemplateChartsField
        enabled={enabled}
        preferredCharts={preferredCharts}
        onToggleChart={onToggleChart}
      />
      <PromptDashboardTemplateSectionsField
        enabled={enabled}
        sectionOrder={sectionOrder}
        onSectionOrderChange={onSectionOrderChange}
      />
    </div>
  </div>
)
