import { FolderOpen, Pencil, Plus, Trash2 } from 'lucide-react'
import { DEFAULT_WORKSPACE_ID } from './sidebarConstants'
import type { WorkspaceSidebarController } from './useWorkspaceSidebarController'
import { WorkspaceDeleteDialog } from './WorkspaceDeleteDialog'
import { WorkspaceFormDialog } from './WorkspaceFormDialog'
import { WorkspaceSummaryCard } from './WorkspaceSummaryCard'

interface WorkspaceSelectorProps {
  controller: WorkspaceSidebarController
  storePanelCount: number
}

export function WorkspaceSelector({
  controller,
  storePanelCount,
}: WorkspaceSelectorProps) {
  const {
    workspaces,
    currentWorkspaceId,
    currentWorkspace,
    currentWorkspacePreset,
    currentWorkspaceConnectorSummary,
    currentWorkspacePanelSummary,
    workspaceDeleteTargets,
    availableMcpConnectors,
    showWorkspaceForm,
    showWorkspaceEditForm,
    showWorkspaceDeleteForm,
    workspaceName,
    workspaceColor,
    workspacePresetWebSearch,
    workspacePresetKnowledgeBase,
    workspacePresetMcpServers,
    workspacePresetDeckTheme,
    workspacePresetDeckSlideCount,
    workspaceEditName,
    workspaceEditDescription,
    workspaceEditColor,
    workspaceEditPresetWebSearch,
    workspaceEditPresetKnowledgeBase,
    workspaceEditPresetMcpServers,
    workspaceEditPresetDeckTheme,
    workspaceEditPresetDeckSlideCount,
    workspaceDeleteTargetId,
    creatingWorkspace,
    updatingWorkspace,
    deletingWorkspace,
    handleSelectWorkspace: onSelectWorkspace,
    openWorkspaceEditor: onOpenWorkspaceEditor,
    openWorkspaceDeletePrompt: onOpenWorkspaceDeletePrompt,
    toggleWorkspaceForm: onToggleWorkspaceForm,
    setWorkspaceName: onWorkspaceNameChange,
    setWorkspaceColor: onWorkspaceColorChange,
    setWorkspacePresetWebSearch: onWorkspacePresetWebSearchChange,
    setWorkspacePresetKnowledgeBase: onWorkspacePresetKnowledgeBaseChange,
    setWorkspacePresetMcpServers: onWorkspacePresetMcpServersChange,
    setWorkspacePresetDeckTheme: onWorkspacePresetDeckThemeChange,
    setWorkspacePresetDeckSlideCount: onWorkspacePresetDeckSlideCountChange,
    cancelWorkspaceCreate: onCancelWorkspaceCreate,
    handleCreateWorkspace: onCreateWorkspace,
    setWorkspaceEditName: onWorkspaceEditNameChange,
    setWorkspaceEditDescription: onWorkspaceEditDescriptionChange,
    setWorkspaceEditColor: onWorkspaceEditColorChange,
    setWorkspaceEditPresetWebSearch: onWorkspaceEditPresetWebSearchChange,
    setWorkspaceEditPresetKnowledgeBase: onWorkspaceEditPresetKnowledgeBaseChange,
    setWorkspaceEditPresetMcpServers: onWorkspaceEditPresetMcpServersChange,
    setWorkspaceEditPresetDeckTheme: onWorkspaceEditPresetDeckThemeChange,
    setWorkspaceEditPresetDeckSlideCount: onWorkspaceEditPresetDeckSlideCountChange,
    cancelWorkspaceEditor: onCancelWorkspaceEditor,
    handleUpdateWorkspace: onUpdateWorkspace,
    setWorkspaceDeleteTargetId: onWorkspaceDeleteTargetChange,
    cancelWorkspaceDelete: onCancelWorkspaceDelete,
    handleDeleteWorkspace: onDeleteWorkspace,
  } = controller

  return (
    <div className="mb-3 rounded-2xl border border-bg-border bg-bg-secondary/60 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-[11px] font-medium text-text-primary">
          <FolderOpen size={13} className="text-accent-blue" />
          Workspace
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onOpenWorkspaceEditor}
            className="rounded-lg p-1 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
            title="Edit workspace"
            disabled={!currentWorkspace}
          >
            <Pencil size={12} />
          </button>
          <button
            type="button"
            onClick={onOpenWorkspaceDeletePrompt}
            className="rounded-lg p-1 text-text-secondary transition-colors hover:bg-accent-red/10 hover:text-accent-red disabled:cursor-not-allowed disabled:opacity-40"
            title={
              currentWorkspace?.workspace_id === DEFAULT_WORKSPACE_ID
                ? 'Default workspace cannot be deleted'
                : 'Delete workspace'
            }
            disabled={!currentWorkspace || currentWorkspace.workspace_id === DEFAULT_WORKSPACE_ID}
          >
            <Trash2 size={12} />
          </button>
          <button
            type="button"
            onClick={onToggleWorkspaceForm}
            className="rounded-lg p-1 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
            title="Create workspace"
          >
            <Plus size={12} />
          </button>
        </div>
      </div>

      <select
        value={currentWorkspaceId ?? ''}
        onChange={(event) => {
          void onSelectWorkspace(event.target.value)
        }}
        className="w-full rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-xs text-text-primary outline-none"
      >
        {workspaces.map((workspace) => (
          <option key={workspace.workspace_id} value={workspace.workspace_id}>
            {workspace.name} ({workspace.session_count} sessions)
          </option>
        ))}
      </select>

      {currentWorkspace && (
        <WorkspaceSummaryCard
          workspace={currentWorkspace}
          preset={currentWorkspacePreset}
          connectorSummary={currentWorkspaceConnectorSummary}
          panelSummary={currentWorkspacePanelSummary}
        />
      )}

      {showWorkspaceForm && (
        <WorkspaceFormDialog
          mode="create"
          name={workspaceName}
          color={workspaceColor}
          presetWebSearch={workspacePresetWebSearch}
          presetKnowledgeBase={workspacePresetKnowledgeBase}
          presetMcpServers={workspacePresetMcpServers}
          presetDeckTheme={workspacePresetDeckTheme}
          presetDeckSlideCount={workspacePresetDeckSlideCount}
          availableMcpConnectors={availableMcpConnectors}
          storePanelCount={storePanelCount}
          saving={creatingWorkspace}
          onNameChange={onWorkspaceNameChange}
          onColorChange={onWorkspaceColorChange}
          onPresetWebSearchChange={onWorkspacePresetWebSearchChange}
          onPresetKnowledgeBaseChange={onWorkspacePresetKnowledgeBaseChange}
          onPresetMcpServersChange={onWorkspacePresetMcpServersChange}
          onPresetDeckThemeChange={onWorkspacePresetDeckThemeChange}
          onPresetDeckSlideCountChange={onWorkspacePresetDeckSlideCountChange}
          onCancel={onCancelWorkspaceCreate}
          onSubmit={onCreateWorkspace}
        />
      )}

      {showWorkspaceEditForm && currentWorkspace && (
        <WorkspaceFormDialog
          mode="edit"
          name={workspaceEditName}
          description={workspaceEditDescription}
          color={workspaceEditColor}
          presetWebSearch={workspaceEditPresetWebSearch}
          presetKnowledgeBase={workspaceEditPresetKnowledgeBase}
          presetMcpServers={workspaceEditPresetMcpServers}
          presetDeckTheme={workspaceEditPresetDeckTheme}
          presetDeckSlideCount={workspaceEditPresetDeckSlideCount}
          availableMcpConnectors={availableMcpConnectors}
          storePanelCount={storePanelCount}
          saving={updatingWorkspace}
          onNameChange={onWorkspaceEditNameChange}
          onDescriptionChange={onWorkspaceEditDescriptionChange}
          onColorChange={onWorkspaceEditColorChange}
          onPresetWebSearchChange={onWorkspaceEditPresetWebSearchChange}
          onPresetKnowledgeBaseChange={onWorkspaceEditPresetKnowledgeBaseChange}
          onPresetMcpServersChange={onWorkspaceEditPresetMcpServersChange}
          onPresetDeckThemeChange={onWorkspaceEditPresetDeckThemeChange}
          onPresetDeckSlideCountChange={onWorkspaceEditPresetDeckSlideCountChange}
          onCancel={onCancelWorkspaceEditor}
          onSubmit={onUpdateWorkspace}
        />
      )}

      {showWorkspaceDeleteForm &&
        currentWorkspace &&
        currentWorkspace.workspace_id !== DEFAULT_WORKSPACE_ID && (
          <WorkspaceDeleteDialog
            deleteTargets={workspaceDeleteTargets}
            targetId={workspaceDeleteTargetId}
            deleting={deletingWorkspace}
            onTargetChange={onWorkspaceDeleteTargetChange}
            onCancel={onCancelWorkspaceDelete}
            onDelete={onDeleteWorkspace}
          />
        )}
    </div>
  )
}
