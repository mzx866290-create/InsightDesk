import React from 'react'
import { Plus } from 'lucide-react'

import { Button } from '../ui/Button'
import type { RolePromptTemplate } from './useRolePrompts'

interface RolePromptLibraryHeaderProps {
  editing: boolean
  onCreate: (template?: RolePromptTemplate) => void
}

export const RolePromptLibraryHeader: React.FC<RolePromptLibraryHeaderProps> = ({
  editing,
  onCreate,
}) => {
  if (editing) return null

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-xs text-text-secondary">
        选择当前生效的 AI 角色，切换后会在下一次对话中生效
      </p>
      <Button
        variant="outline"
        onClick={() => onCreate()}
        className="gap-1.5 text-xs"
        data-testid="settings-role-prompt-create"
      >
        <Plus size={12} />
        新建角色
      </Button>
    </div>
  )
}
