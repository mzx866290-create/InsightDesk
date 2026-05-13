import type { ReactNode } from 'react'

interface PromptDashboardTemplateFieldLabelProps {
  children: ReactNode
  hint?: ReactNode
}

export function PromptDashboardTemplateFieldLabel({
  children,
  hint,
}: PromptDashboardTemplateFieldLabelProps) {
  return (
    <label className="block text-xs font-medium text-text-secondary mb-1.5">
      {children}
      {hint ? (
        <span className="ml-1.5 text-text-secondary/50 font-normal">{hint}</span>
      ) : null}
    </label>
  )
}
