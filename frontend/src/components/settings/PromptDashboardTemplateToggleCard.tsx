import { ToggleLeft, ToggleRight } from 'lucide-react'

import type { PromptDashboardTemplateEnabledProps } from './PromptDashboardTemplateFieldTypes'

interface PromptDashboardTemplateToggleCardProps
  extends PromptDashboardTemplateEnabledProps {
  onEnabledChange: () => void
}

export function PromptDashboardTemplateToggleCard({
  enabled,
  onEnabledChange,
}: PromptDashboardTemplateToggleCardProps) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-bg-border bg-bg-secondary/40 px-3 py-2.5">
      <div>
        <p className="text-xs font-medium text-text-primary">看板卡片</p>
        <p className="mt-1 text-[11px] text-text-secondary/65">
          如果这个角色不需要生成看板卡片，可以在这里关闭。
        </p>
      </div>
      <button
        type="button"
        data-testid="settings-prompt-dashboard-enabled"
        onClick={onEnabledChange}
        className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[11px] transition-colors ${
          enabled
            ? 'border-accent-blue/35 bg-accent-blue/12 text-accent-blue'
            : 'border-bg-border bg-bg-primary text-text-secondary'
        }`}
        aria-pressed={enabled}
        title={enabled ? '禁用看板卡片' : '启用看板卡片'}
      >
        {enabled ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
        {enabled ? '已启用' : '已禁用'}
      </button>
    </div>
  )
}
