import { PromptDashboardTemplateFieldLabel } from './PromptDashboardTemplateFieldLabel'
import type { PromptDashboardTemplateEnabledProps } from './PromptDashboardTemplateFieldTypes'

interface PromptDashboardTemplateTextFieldsProps
  extends PromptDashboardTemplateEnabledProps {
  titleHint: string
  audienceTone: string
  onTitleHintChange: (value: string) => void
  onAudienceToneChange: (value: string) => void
}

export function PromptDashboardTemplateTextFields({
  enabled,
  titleHint,
  audienceTone,
  onTitleHintChange,
  onAudienceToneChange,
}: PromptDashboardTemplateTextFieldsProps) {
  return (
    <>
      <div>
        <PromptDashboardTemplateFieldLabel>
          看板标题提示
        </PromptDashboardTemplateFieldLabel>
        <input
          data-testid="settings-prompt-dashboard-title-hint"
          className="input-base w-full text-sm"
          placeholder="例如：管理层经营分析看板"
          value={titleHint}
          onChange={(event) => onTitleHintChange(event.target.value)}
          disabled={!enabled}
        />
      </div>

      <div>
        <PromptDashboardTemplateFieldLabel>
          受众语气
        </PromptDashboardTemplateFieldLabel>
        <input
          data-testid="settings-prompt-dashboard-audience-tone"
          className="input-base w-full text-sm"
          placeholder="例如：专业、直观、适合业务汇报"
          value={audienceTone}
          onChange={(event) => onAudienceToneChange(event.target.value)}
          disabled={!enabled}
        />
      </div>
    </>
  )
}
