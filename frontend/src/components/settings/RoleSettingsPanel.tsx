import React from 'react'
import { IdentityAdminPanel } from '../admin/IdentityAdminPanel'
import { ResourceAccessPanel } from '../admin/ResourceAccessPanel'
import { RolePromptEditorPanel } from './RolePromptEditorPanel'
import { RolePromptLibraryPanel } from './RolePromptLibraryPanel'
import type { RolePromptTemplate, RolePromptsController } from './useRolePrompts'

interface RoleSettingsPanelProps {
  rolePrompts: RolePromptsController
  quickTemplates: RolePromptTemplate[]
}

export function RoleSettingsPanel({ rolePrompts, quickTemplates }: RoleSettingsPanelProps) {
  return (
    <div className="space-y-4" data-testid="settings-roles-panel">
      <IdentityAdminPanel />
      <ResourceAccessPanel />

      {(rolePrompts.isCreating || rolePrompts.editingPrompt) ? (
        <RolePromptEditorPanel
          isCreating={rolePrompts.isCreating}
          editingPrompt={rolePrompts.editingPrompt}
          name={rolePrompts.promptName}
          content={rolePrompts.promptContent}
          vectorStoreId={rolePrompts.promptVectorStoreId}
          knowledgeBases={rolePrompts.knowledgeBases}
          loadingKnowledgeBases={rolePrompts.loadingKnowledgeBases}
          dashboardFieldsProps={rolePrompts.dashboardFieldsProps}
          saving={rolePrompts.promptSaving}
          onNameChange={rolePrompts.setPromptName}
          onContentChange={rolePrompts.setPromptContent}
          onVectorStoreIdChange={rolePrompts.setPromptVectorStoreId}
          onSave={rolePrompts.savePrompt}
          onCancel={rolePrompts.cancelEdit}
        />
      ) : (
        <RolePromptLibraryPanel
          loading={rolePrompts.loadingPrompts}
          prompts={rolePrompts.prompts}
          editing={rolePrompts.isCreating || Boolean(rolePrompts.editingPrompt)}
          activatingId={rolePrompts.activatingId}
          deletingPromptId={rolePrompts.deletingPromptId}
          activateStatus={rolePrompts.activateStatus}
          quickTemplates={quickTemplates}
          onCreate={rolePrompts.startCreate}
          onActivate={rolePrompts.activatePrompt}
          onEdit={rolePrompts.startEdit}
          onDelete={rolePrompts.deletePrompt}
        />
      )}
    </div>
  )
}
