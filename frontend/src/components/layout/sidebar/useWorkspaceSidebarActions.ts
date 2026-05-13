import {
  activateWorkspace,
  createWorkspace,
  deleteWorkspace as deleteWorkspaceRequest,
  getWorkspaces,
  updateWorkspace as updateWorkspaceRequest,
} from '../../../api/client'
import type { Session, Workspace } from '../../../api/client'
import { useChatStore } from '../../../stores/chatStore'
import type { Panel } from '../../../stores/chatStoreModel'
import {
  DEFAULT_WORKSPACE_ID,
  type WorkspaceDeckTheme,
} from './sidebarConstants'
import type { WorkspaceSidebarForms } from './useWorkspaceSidebarForms'

interface UseWorkspaceSidebarActionsOptions {
  forms: WorkspaceSidebarForms
  workspaces: Workspace[]
  currentWorkspaceId: string | null
  currentWorkspace: Workspace | null
  workspaceDeleteTargets: Workspace[]
  storePanels: Panel[]
  applyWorkspacePreset: (workspace: Workspace | null) => void
  setError: (message: string) => void
  setCreatingWorkspace: (creating: boolean) => void
  setUpdatingWorkspace: (updating: boolean) => void
  setDeletingWorkspace: (deleting: boolean) => void
}

export function useWorkspaceSidebarActions({
  forms,
  workspaces,
  currentWorkspaceId,
  currentWorkspace,
  workspaceDeleteTargets,
  storePanels,
  applyWorkspacePreset,
  setError,
  setCreatingWorkspace,
  setUpdatingWorkspace,
  setDeletingWorkspace,
}: UseWorkspaceSidebarActionsOptions) {
  const {
    setWorkspaces,
    setCurrentWorkspace,
    updateWorkspace: updateWorkspaceInStore,
  } = useChatStore()

  const buildWorkspacePresetPayload = (
    toolConfig: {
      web_search_enabled: boolean
      knowledge_base_enabled: boolean
      mcp_servers_enabled: string[]
    },
    outputPreset: {
      deck_theme: WorkspaceDeckTheme
      target_slide_count: number
    },
  ) => ({
    default_panels: storePanels.map((panel) => panel.modelConfig),
    tool_config: toolConfig,
    output_preset: outputPreset,
  })

  const handleSelectWorkspace = async (workspaceId: string) => {
    if (!workspaceId || workspaceId === currentWorkspaceId) return
    setError('')
    forms.closeWorkspaceSecondaryForms()
    try {
      const activated = await activateWorkspace(workspaceId)
      setCurrentWorkspace(activated.workspace_id)
      applyWorkspacePreset(activated)
      setWorkspaces(
        workspaces.map((workspace) =>
          workspace.workspace_id === activated.workspace_id
            ? activated
            : { ...workspace, is_active: false },
        ),
      )
    } catch (workspaceError) {
      console.error(workspaceError)
      setError((workspaceError as Error).message ?? 'Failed to switch workspace.')
    }
  }

  const handleCreateWorkspace = async () => {
    const name = forms.workspaceName.trim()
    if (!name) {
      setError('Workspace name is required.')
      return
    }
    setCreatingWorkspace(true)
    setError('')
    try {
      const workspace = await createWorkspace({
        name,
        color: forms.workspaceColor,
        activate: true,
        preset: buildWorkspacePresetPayload(
          {
            web_search_enabled: forms.workspacePresetWebSearch,
            knowledge_base_enabled: forms.workspacePresetKnowledgeBase,
            mcp_servers_enabled: forms.workspacePresetMcpServers,
          },
          {
            deck_theme: forms.workspacePresetDeckTheme,
            target_slide_count: forms.workspacePresetDeckSlideCount,
          },
        ),
      })
      setWorkspaces(
        [
          workspace,
          ...workspaces.filter((item) => item.workspace_id !== workspace.workspace_id).map((item) => ({
            ...item,
            is_active: false,
          })),
        ],
      )
      setCurrentWorkspace(workspace.workspace_id)
      applyWorkspacePreset(workspace)
      forms.resetWorkspaceCreateAfterSave(workspace)
    } catch (workspaceError) {
      console.error(workspaceError)
      setError((workspaceError as Error).message ?? 'Failed to create workspace.')
    } finally {
      setCreatingWorkspace(false)
    }
  }

  const handleUpdateWorkspace = async () => {
    if (!currentWorkspace) return
    const name = forms.workspaceEditName.trim()
    if (!name) {
      setError('Workspace name is required.')
      return
    }

    setUpdatingWorkspace(true)
    setError('')
    try {
      const updated = await updateWorkspaceRequest(currentWorkspace.workspace_id, {
        name,
        description: forms.workspaceEditDescription.trim(),
        color: forms.workspaceEditColor,
        preset: buildWorkspacePresetPayload(
          {
            web_search_enabled: forms.workspaceEditPresetWebSearch,
            knowledge_base_enabled: forms.workspaceEditPresetKnowledgeBase,
            mcp_servers_enabled: forms.workspaceEditPresetMcpServers,
          },
          {
            deck_theme: forms.workspaceEditPresetDeckTheme,
            target_slide_count: forms.workspaceEditPresetDeckSlideCount,
          },
        ),
      })
      updateWorkspaceInStore(updated.workspace_id, updated)
      if (updated.workspace_id === currentWorkspaceId) {
        applyWorkspacePreset(updated)
      }
      forms.cancelWorkspaceEditor()
    } catch (workspaceError) {
      console.error(workspaceError)
      setError((workspaceError as Error).message ?? 'Failed to update workspace.')
    } finally {
      setUpdatingWorkspace(false)
    }
  }

  const handleDeleteWorkspace = async () => {
    if (!currentWorkspace || currentWorkspace.workspace_id === DEFAULT_WORKSPACE_ID) return

    const targetWorkspaceId =
      forms.workspaceDeleteTargetId.trim() ||
      workspaceDeleteTargets[0]?.workspace_id ||
      DEFAULT_WORKSPACE_ID

    setDeletingWorkspace(true)
    setError('')
    try {
      const result = await deleteWorkspaceRequest(currentWorkspace.workspace_id, {
        target_workspace_id: targetWorkspaceId,
      })
      const payload = await getWorkspaces()
      setWorkspaces(payload.workspaces)
      setCurrentWorkspace(result.target_workspace_id)
      applyWorkspacePreset(
        payload.workspaces.find((item) => item.workspace_id === result.target_workspace_id) ?? null,
      )
      forms.cancelWorkspaceDelete()
      forms.cancelWorkspaceEditor()
    } catch (workspaceError) {
      console.error(workspaceError)
      setError((workspaceError as Error).message ?? 'Failed to delete workspace.')
    } finally {
      setDeletingWorkspace(false)
    }
  }

  const syncWorkspaceForSession = async (session: Session, force = false) => {
    if (!force && session.workspace_id === currentWorkspaceId) return
    if (session.workspace_id === currentWorkspaceId) return
    try {
      const activated = await activateWorkspace(session.workspace_id)
      setCurrentWorkspace(activated.workspace_id)
      applyWorkspacePreset(activated)
      setWorkspaces(
        workspaces.map((workspace) =>
          workspace.workspace_id === activated.workspace_id
            ? activated
            : { ...workspace, is_active: false },
        ),
      )
    } catch (workspaceError) {
      console.error(workspaceError)
    }
  }

  return {
    handleSelectWorkspace,
    handleCreateWorkspace,
    handleUpdateWorkspace,
    handleDeleteWorkspace,
    syncWorkspaceForSession,
  }
}
