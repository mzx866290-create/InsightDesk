import { useState } from 'react'
import type { Workspace } from '../../../api/client'
import {
  DEFAULT_ENABLED_MCP_SERVERS,
  DEFAULT_WORKSPACE_ID,
  type WorkspaceDeckTheme,
} from './sidebarConstants'

interface UseWorkspaceSidebarFormsOptions {
  currentWorkspace: Workspace | null
  workspaceDeleteTargets: Workspace[]
  webSearchEnabled: boolean
  knowledgeBaseEnabled: boolean
  enabledMcpServers: string[]
  setError: (message: string) => void
}

export function useWorkspaceSidebarForms({
  currentWorkspace,
  workspaceDeleteTargets,
  webSearchEnabled,
  knowledgeBaseEnabled,
  enabledMcpServers,
  setError,
}: UseWorkspaceSidebarFormsOptions) {
  const [showWorkspaceForm, setShowWorkspaceForm] = useState(false)
  const [showWorkspaceEditForm, setShowWorkspaceEditForm] = useState(false)
  const [showWorkspaceDeleteForm, setShowWorkspaceDeleteForm] = useState(false)
  const [workspaceName, setWorkspaceName] = useState('')
  const [workspaceColor, setWorkspaceColor] = useState<Workspace['color']>('blue')
  const [workspacePresetWebSearch, setWorkspacePresetWebSearch] = useState(false)
  const [workspacePresetKnowledgeBase, setWorkspacePresetKnowledgeBase] = useState(true)
  const [workspacePresetMcpServers, setWorkspacePresetMcpServers] = useState<string[]>(
    DEFAULT_ENABLED_MCP_SERVERS,
  )
  const [workspacePresetDeckTheme, setWorkspacePresetDeckTheme] =
    useState<WorkspaceDeckTheme>('default')
  const [workspacePresetDeckSlideCount, setWorkspacePresetDeckSlideCount] = useState(8)
  const [workspaceEditName, setWorkspaceEditName] = useState('')
  const [workspaceEditDescription, setWorkspaceEditDescription] = useState('')
  const [workspaceEditColor, setWorkspaceEditColor] = useState<Workspace['color']>('blue')
  const [workspaceEditPresetWebSearch, setWorkspaceEditPresetWebSearch] = useState(false)
  const [workspaceEditPresetKnowledgeBase, setWorkspaceEditPresetKnowledgeBase] = useState(true)
  const [workspaceEditPresetMcpServers, setWorkspaceEditPresetMcpServers] = useState<string[]>(
    DEFAULT_ENABLED_MCP_SERVERS,
  )
  const [workspaceEditPresetDeckTheme, setWorkspaceEditPresetDeckTheme] =
    useState<WorkspaceDeckTheme>('default')
  const [workspaceEditPresetDeckSlideCount, setWorkspaceEditPresetDeckSlideCount] = useState(8)
  const [workspaceDeleteTargetId, setWorkspaceDeleteTargetId] =
    useState(DEFAULT_WORKSPACE_ID)

  const resetCreatePreset = () => {
    setWorkspacePresetWebSearch(webSearchEnabled)
    setWorkspacePresetKnowledgeBase(knowledgeBaseEnabled)
    setWorkspacePresetMcpServers(enabledMcpServers)
    setWorkspacePresetDeckTheme('default')
    setWorkspacePresetDeckSlideCount(8)
  }

  const toggleWorkspaceForm = () => {
    setShowWorkspaceForm((current) => {
      const next = !current
      if (next) {
        resetCreatePreset()
      }
      return next
    })
    setShowWorkspaceEditForm(false)
    setShowWorkspaceDeleteForm(false)
    setError('')
  }

  const cancelWorkspaceCreate = () => {
    setShowWorkspaceForm(false)
    setWorkspaceName('')
    setWorkspaceColor('blue')
    resetCreatePreset()
  }

  const resetWorkspaceCreateAfterSave = (workspace: Workspace) => {
    setWorkspaceName('')
    setWorkspaceColor('blue')
    setWorkspacePresetWebSearch(webSearchEnabled)
    setWorkspacePresetKnowledgeBase(knowledgeBaseEnabled)
    setWorkspacePresetMcpServers(
      workspace.preset?.tool_config.mcp_servers_enabled ?? DEFAULT_ENABLED_MCP_SERVERS,
    )
    setWorkspacePresetDeckTheme('default')
    setWorkspacePresetDeckSlideCount(8)
    setShowWorkspaceForm(false)
    setShowWorkspaceEditForm(false)
    setShowWorkspaceDeleteForm(false)
  }

  const openWorkspaceEditor = () => {
    if (!currentWorkspace) return
    setWorkspaceEditName(currentWorkspace.name)
    setWorkspaceEditDescription(currentWorkspace.description)
    setWorkspaceEditColor(currentWorkspace.color)
    setWorkspaceEditPresetWebSearch(
      currentWorkspace.preset?.tool_config.web_search_enabled ?? webSearchEnabled,
    )
    setWorkspaceEditPresetKnowledgeBase(
      currentWorkspace.preset?.tool_config.knowledge_base_enabled ?? knowledgeBaseEnabled,
    )
    setWorkspaceEditPresetMcpServers(
      currentWorkspace.preset?.tool_config.mcp_servers_enabled ?? enabledMcpServers,
    )
    setWorkspaceEditPresetDeckTheme(
      currentWorkspace.preset?.output_preset.deck_theme ?? 'default',
    )
    setWorkspaceEditPresetDeckSlideCount(
      currentWorkspace.preset?.output_preset.target_slide_count ?? 8,
    )
    setShowWorkspaceEditForm(true)
    setShowWorkspaceForm(false)
    setShowWorkspaceDeleteForm(false)
    setError('')
  }

  const cancelWorkspaceEditor = () => {
    setShowWorkspaceEditForm(false)
    setWorkspaceEditName('')
    setWorkspaceEditDescription('')
    setWorkspaceEditColor('blue')
    setWorkspaceEditPresetWebSearch(false)
    setWorkspaceEditPresetKnowledgeBase(true)
    setWorkspaceEditPresetMcpServers(enabledMcpServers)
    setWorkspaceEditPresetDeckTheme('default')
    setWorkspaceEditPresetDeckSlideCount(8)
  }

  const openWorkspaceDeletePrompt = () => {
    if (!currentWorkspace || currentWorkspace.workspace_id === DEFAULT_WORKSPACE_ID) return
    setWorkspaceDeleteTargetId(workspaceDeleteTargets[0]?.workspace_id ?? DEFAULT_WORKSPACE_ID)
    setShowWorkspaceDeleteForm(true)
    setShowWorkspaceEditForm(false)
    setShowWorkspaceForm(false)
    setError('')
  }

  const cancelWorkspaceDelete = () => {
    setShowWorkspaceDeleteForm(false)
    setWorkspaceDeleteTargetId(DEFAULT_WORKSPACE_ID)
  }

  const closeWorkspaceSecondaryForms = () => {
    setShowWorkspaceEditForm(false)
    setShowWorkspaceDeleteForm(false)
  }

  return {
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
    toggleWorkspaceForm,
    cancelWorkspaceCreate,
    resetWorkspaceCreateAfterSave,
    openWorkspaceEditor,
    cancelWorkspaceEditor,
    openWorkspaceDeletePrompt,
    cancelWorkspaceDelete,
    closeWorkspaceSecondaryForms,
    setWorkspaceName,
    setWorkspaceColor,
    setWorkspacePresetWebSearch,
    setWorkspacePresetKnowledgeBase,
    setWorkspacePresetMcpServers,
    setWorkspacePresetDeckTheme,
    setWorkspacePresetDeckSlideCount,
    setWorkspaceEditName,
    setWorkspaceEditDescription,
    setWorkspaceEditColor,
    setWorkspaceEditPresetWebSearch,
    setWorkspaceEditPresetKnowledgeBase,
    setWorkspaceEditPresetMcpServers,
    setWorkspaceEditPresetDeckTheme,
    setWorkspaceEditPresetDeckSlideCount,
    setWorkspaceDeleteTargetId,
  }
}

export type WorkspaceSidebarForms = ReturnType<typeof useWorkspaceSidebarForms>
