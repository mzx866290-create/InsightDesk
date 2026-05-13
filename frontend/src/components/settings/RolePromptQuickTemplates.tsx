import React from 'react'

import type { RolePromptTemplate } from './useRolePrompts'

interface RolePromptQuickTemplatesProps {
  editing: boolean
  quickTemplates: RolePromptTemplate[]
  onCreate: (template?: RolePromptTemplate) => void
}

export const RolePromptQuickTemplates: React.FC<RolePromptQuickTemplatesProps> = ({
  editing,
  quickTemplates,
  onCreate,
}) => {
  if (editing) return null

  return (
    <div className="border-t border-bg-border pt-2">
      <p className="mb-2 text-[11px] text-text-secondary">快捷模板</p>
      <div className="flex flex-wrap gap-2">
        {quickTemplates.map((template) => (
          <button
            key={template.name}
            type="button"
            onClick={() => onCreate(template)}
            data-testid="settings-role-prompt-quick-template"
            data-template-name={template.name}
            className="rounded-lg border border-bg-border px-2.5 py-1 text-[11px] text-text-secondary transition-colors hover:border-accent-blue/40 hover:bg-accent-blue/5 hover:text-text-primary"
          >
            + {template.name}
          </button>
        ))}
      </div>
    </div>
  )
}
