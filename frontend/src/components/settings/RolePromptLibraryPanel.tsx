import React from 'react'

import type { SystemPrompt } from '../../api/client'
import { RolePromptLibraryHeader } from './RolePromptLibraryHeader'
import { RolePromptLibraryRow } from './RolePromptLibraryRow'
import { RolePromptQuickTemplates } from './RolePromptQuickTemplates'
import type { RolePromptTemplate } from './useRolePrompts'

interface RolePromptLibraryPanelProps {
  loading: boolean
  prompts: SystemPrompt[]
  editing: boolean
  activatingId: string | null
  deletingPromptId: string | null
  activateStatus: Record<string, string>
  quickTemplates: RolePromptTemplate[]
  onCreate: (template?: RolePromptTemplate) => void
  onActivate: (id: string) => void
  onEdit: (prompt: SystemPrompt) => void
  onDelete: (id: string) => void
}

export const RolePromptLibraryPanel: React.FC<RolePromptLibraryPanelProps> = ({
  loading,
  prompts,
  editing,
  activatingId,
  deletingPromptId,
  activateStatus,
  quickTemplates,
  onCreate,
  onActivate,
  onEdit,
  onDelete,
}) => (
  <>
    <RolePromptLibraryHeader editing={editing} onCreate={onCreate} />

    {loading ? (
      <div className="flex justify-center py-6">
        <span className="w-5 h-5 border-2 border-accent-blue border-t-transparent rounded-full animate-spin" />
      </div>
    ) : (
      <div className="space-y-2">
        {prompts.map((prompt) => (
          <RolePromptLibraryRow
            key={prompt.id}
            prompt={prompt}
            activating={activatingId === prompt.id}
            deleting={deletingPromptId === prompt.id}
            activateStatus={activateStatus[prompt.id]}
            onActivate={onActivate}
            onEdit={onEdit}
            onDelete={onDelete}
          />
        ))}
      </div>
    )}

    <RolePromptQuickTemplates
      editing={editing}
      quickTemplates={quickTemplates}
      onCreate={onCreate}
    />
  </>
)
