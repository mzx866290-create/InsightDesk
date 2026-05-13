import React from 'react'
import type { KnowledgeBase, SystemPrompt } from '../../api/client'
import { Button } from '../ui/Button'
import {
  PromptDashboardTemplateFields,
  type PromptDashboardTemplateFieldsProps,
} from './PromptDashboardTemplateFields'

interface RolePromptEditorPanelProps {
  isCreating: boolean
  editingPrompt: SystemPrompt | null
  name: string
  content: string
  vectorStoreId: string
  knowledgeBases: KnowledgeBase[]
  loadingKnowledgeBases: boolean
  dashboardFieldsProps: PromptDashboardTemplateFieldsProps
  saving: boolean
  onNameChange: (value: string) => void
  onContentChange: (value: string) => void
  onVectorStoreIdChange: (value: string) => void
  onSave: () => void
  onCancel: () => void
}

export const RolePromptEditorPanel: React.FC<RolePromptEditorPanelProps> = ({
  isCreating,
  editingPrompt,
  name,
  content,
  vectorStoreId,
  knowledgeBases,
  loadingKnowledgeBases,
  dashboardFieldsProps,
  saving,
  onNameChange,
  onContentChange,
  onVectorStoreIdChange,
  onSave,
  onCancel,
}) => (
  <div className="grid gap-4 rounded-xl border border-bg-border bg-bg-tertiary p-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(18rem,0.85fr)]">
    <p className="text-xs font-medium text-text-primary lg:col-span-2">
      {isCreating ? '新建角色' : `编辑：${editingPrompt?.name}`}
    </p>

    <input
      data-testid="settings-role-prompt-name"
      className="input-base w-full text-sm"
      placeholder="角色名称"
      value={name}
      onChange={(event) => onNameChange(event.target.value)}
      maxLength={40}
    />

    <div className="relative lg:row-span-3">
      <textarea
        data-testid="settings-role-prompt-content"
        className="input-base w-full text-sm resize-none leading-relaxed"
        placeholder="描述这个 AI 角色的职责、能力边界和回答风格..."
        value={content}
        onChange={(event) => onContentChange(event.target.value)}
        rows={5}
      />
      <span className="absolute bottom-2 right-2.5 text-[10px] text-text-secondary/40">
        {content.length} 字
      </span>
    </div>

    <div>
      <label className="block text-xs font-medium text-text-secondary mb-1.5">
        知识库绑定
        <span className="ml-1.5 text-text-secondary/50 font-normal">（可选，切换角色时自动加载）</span>
      </label>
      {loadingKnowledgeBases ? (
        <span className="text-xs text-text-secondary">正在加载知识库列表...</span>
      ) : (
        <select
          data-testid="settings-role-prompt-kb-select"
          className="input-base w-full text-sm"
          value={vectorStoreId}
          onChange={(event) => onVectorStoreIdChange(event.target.value)}
        >
          <option value="">不绑定（使用默认知识库）</option>
          {knowledgeBases.map((knowledgeBase) => (
            <option key={knowledgeBase.id} value={knowledgeBase.id}>
              {knowledgeBase.name}（{knowledgeBase.doc_count} 个切片）
              {!knowledgeBase.has_index ? ' [无索引]' : ''}
            </option>
          ))}
        </select>
      )}
    </div>

    <PromptDashboardTemplateFields {...dashboardFieldsProps} />

    <div className="flex flex-wrap gap-2 pt-1 lg:col-span-2">
      <Button
        variant="primary"
        onClick={onSave}
        loading={saving}
        disabled={!name.trim() || !content.trim()}
        data-testid="settings-role-prompt-save"
      >
        保存
      </Button>
      <Button
        variant="ghost"
        onClick={onCancel}
        data-testid="settings-role-prompt-cancel"
      >
        取消
      </Button>
    </div>
  </div>
)
