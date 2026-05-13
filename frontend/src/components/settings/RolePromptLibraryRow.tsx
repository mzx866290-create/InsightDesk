import React from 'react'
import { Check, Database, Pencil, Trash2, UserCog, Zap } from 'lucide-react'

import type { SystemPrompt } from '../../api/client'

interface RolePromptLibraryRowProps {
  prompt: SystemPrompt
  activating: boolean
  deleting: boolean
  activateStatus: string | undefined
  onActivate: (id: string) => void
  onEdit: (prompt: SystemPrompt) => void
  onDelete: (id: string) => void
}

function hasDashboardTemplate(prompt: SystemPrompt): boolean {
  return Boolean(
    prompt.dashboard_template &&
    Object.keys(prompt.dashboard_template).length > 0,
  )
}

function isDashboardEnabled(prompt: SystemPrompt): boolean {
  return prompt.dashboard_template?.enabled !== false
}

function getKnowledgeBaseStatusLabel(status: string): string {
  if (status === 'loaded') return '已加载'
  if (status === 'error') return '加载失败'
  return status
}

function getKnowledgeBaseStatusClassName(status: string): string {
  if (status === 'loaded') return 'bg-accent-green/15 text-accent-green'
  if (status === 'error') return 'bg-accent-red/15 text-accent-red'
  return 'bg-bg-tertiary text-text-secondary'
}

export const RolePromptLibraryRow: React.FC<RolePromptLibraryRowProps> = ({
  prompt,
  activating,
  deleting,
  activateStatus,
  onActivate,
  onEdit,
  onDelete,
}) => (
  <div
    data-testid="settings-role-prompt-row"
    data-prompt-id={prompt.id}
    className={`rounded-xl border px-4 py-3 transition-colors ${
      prompt.is_active
        ? 'border-accent-blue/50 bg-accent-blue/5'
        : 'border-bg-border bg-bg-tertiary/40 hover:bg-bg-tertiary/70'
    }`}
  >
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <UserCog size={13} className={prompt.is_active ? 'text-accent-blue' : 'text-text-secondary'} />
          <span className="truncate text-sm font-medium text-text-primary">{prompt.name}</span>
          {prompt.is_active && (
            <span className="shrink-0 rounded-full bg-accent-blue/20 px-1.5 py-0.5 text-[10px] font-medium text-accent-blue">
              当前使用
            </span>
          )}
          {prompt.is_default && (
            <span className="shrink-0 text-[10px] text-text-secondary/50">内置</span>
          )}
          {prompt.vector_store_id && (
            <span className="flex shrink-0 items-center gap-1 rounded-full bg-accent-green/15 px-1.5 py-0.5 text-[10px] text-accent-green">
              <Database size={9} />
              已绑定知识库
            </span>
          )}
          {hasDashboardTemplate(prompt) && (
            <span className={`flex shrink-0 items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] ${
              isDashboardEnabled(prompt)
                ? 'bg-accent-blue/15 text-accent-blue'
                : 'bg-bg-secondary text-text-secondary'
            }`}>
              <Zap size={9} />
              {isDashboardEnabled(prompt) ? '看板已启用' : '看板已关闭'}
            </span>
          )}
          {activateStatus && (
            <span className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] ${getKnowledgeBaseStatusClassName(activateStatus)}`}>
              知识库 {getKnowledgeBaseStatusLabel(activateStatus)}
            </span>
          )}
        </div>
        <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-text-secondary">
          {prompt.content}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1 self-end sm:self-auto">
        {!prompt.is_active && (
          <button
            type="button"
            onClick={() => onActivate(prompt.id)}
            disabled={activating}
            data-testid="settings-role-prompt-activate"
            data-prompt-id={prompt.id}
            className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-accent-blue/10 hover:text-accent-blue disabled:opacity-50"
            title="设为当前角色"
          >
            {activating ? (
              <span className="block h-3.5 w-3.5 animate-spin rounded-full border border-current border-t-transparent" />
            ) : (
              <Check size={13} />
            )}
          </button>
        )}
        <button
          type="button"
          onClick={() => onEdit(prompt)}
          data-testid="settings-role-prompt-edit"
          data-prompt-id={prompt.id}
          className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
          title="编辑"
        >
          <Pencil size={12} />
        </button>
        {!prompt.is_default && (
          <button
            type="button"
            onClick={() => onDelete(prompt.id)}
            disabled={deleting}
            data-testid="settings-role-prompt-delete"
            data-prompt-id={prompt.id}
            className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-accent-red/10 hover:text-accent-red disabled:opacity-50"
            title="删除"
          >
            {deleting ? (
              <span className="block h-3.5 w-3.5 animate-spin rounded-full border border-current border-t-transparent" />
            ) : (
              <Trash2 size={12} />
            )}
          </button>
        )}
      </div>
    </div>
  </div>
)
