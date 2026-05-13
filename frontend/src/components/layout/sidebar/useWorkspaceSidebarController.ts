import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  getMcpConnectors,
  getWorkspaces,
} from '../../../api/client'
import type { McpConnector, Workspace } from '../../../api/client'
import { useChatStore } from '../../../stores/chatStore'
import type { Panel } from '../../../stores/chatStoreModel'
import { useWorkspaceSidebarActions } from './useWorkspaceSidebarActions'
import { useWorkspaceSidebarForms } from './useWorkspaceSidebarForms'

interface UseWorkspaceSidebarControllerOptions {
  storePanels: Panel[]
  webSearchEnabled: boolean
  knowledgeBaseEnabled: boolean
  enabledMcpServers: string[]
  setError: (message: string) => void
}

export function useWorkspaceSidebarController({
  storePanels,
  webSearchEnabled,
  knowledgeBaseEnabled,
  enabledMcpServers,
  setError,
}: UseWorkspaceSidebarControllerOptions) {
  const {
    workspaces,
    currentWorkspaceId,
    setWorkspaces,
    setCurrentWorkspace,
    setPanels,
    setWebSearchEnabled,
    setKnowledgeBaseEnabled,
    setEnabledMcpServers,
  } = useChatStore()

  const [workspaceReady, setWorkspaceReady] = useState(false)
  const [creatingWorkspace, setCreatingWorkspace] = useState(false)
  const [updatingWorkspace, setUpdatingWorkspace] = useState(false)
  const [deletingWorkspace, setDeletingWorkspace] = useState(false)
  const [availableMcpConnectors, setAvailableMcpConnectors] = useState<McpConnector[]>([])

  const currentWorkspace = useMemo(
    () =>
      workspaces.find((workspace) => workspace.workspace_id === currentWorkspaceId) ?? null,
    [currentWorkspaceId, workspaces],
  )
  const currentWorkspacePreset = currentWorkspace?.preset
  const currentWorkspacePanelSummary = useMemo(
    () =>
      (currentWorkspacePreset?.default_panels ?? [])
        .map((panel) => panel.model)
        .filter((model) => model.trim().length > 0)
        .join(' / '),
    [currentWorkspacePreset],
  )
  const workspaceNameMap = useMemo(
    () => new Map(workspaces.map((workspace) => [workspace.workspace_id, workspace.name])),
    [workspaces],
  )
  const workspaceDeleteTargets = useMemo(
    () =>
      workspaces.filter((workspace) => workspace.workspace_id !== currentWorkspace?.workspace_id),
    [currentWorkspace?.workspace_id, workspaces],
  )
  const connectorLabelMap = useMemo(
    () => new Map(availableMcpConnectors.map((connector) => [connector.name, connector.label])),
    [availableMcpConnectors],
  )
  const currentWorkspaceConnectorSummary = useMemo(() => {
    const connectorNames = currentWorkspacePreset?.tool_config.mcp_servers_enabled ?? []
    if (connectorNames.length === 0) {
      return 'None enabled'
    }
    return connectorNames
      .map((name) => connectorLabelMap.get(name) ?? name)
      .join(' / ')
  }, [connectorLabelMap, currentWorkspacePreset])

  const forms = useWorkspaceSidebarForms({
    currentWorkspace,
    workspaceDeleteTargets,
    webSearchEnabled,
    knowledgeBaseEnabled,
    enabledMcpServers,
    setError,
  })

  const applyWorkspacePreset = useCallback((workspace: Workspace | null) => {
    if (!workspace?.preset) return

    setWebSearchEnabled(workspace.preset.tool_config.web_search_enabled)
    setKnowledgeBaseEnabled(workspace.preset.tool_config.knowledge_base_enabled)
    setEnabledMcpServers(workspace.preset.tool_config.mcp_servers_enabled)

    // Workspace presets own the default panel topology; apply it in one place.
    if (workspace.preset.default_panels.length > 0) {
      setPanels(
        workspace.preset.default_panels.map((panelConfig) => ({
          id: panelConfig.panel_id,
          modelConfig: panelConfig,
          messages: [],
        })),
      )
    }
  }, [setEnabledMcpServers, setKnowledgeBaseEnabled, setPanels, setWebSearchEnabled])

  const actions = useWorkspaceSidebarActions({
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
  })

  useEffect(() => {
    let cancelled = false

    const loadConnectorCatalog = async () => {
      try {
        const payload = await getMcpConnectors()
        if (cancelled) return
        setAvailableMcpConnectors(payload.connectors)
      } catch (loadError) {
        console.error(loadError)
      }
    }

    void loadConnectorCatalog()

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      try {
        const payload = await getWorkspaces()
        if (!cancelled) {
          setWorkspaces(payload.workspaces)
          const nextWorkspaceId =
            currentWorkspaceId &&
            payload.workspaces.some((item) => item.workspace_id === currentWorkspaceId)
              ? currentWorkspaceId
              : payload.active_workspace_id ?? payload.workspaces[0]?.workspace_id ?? null
          setCurrentWorkspace(nextWorkspaceId)
          applyWorkspacePreset(
            payload.workspaces.find((item) => item.workspace_id === nextWorkspaceId) ?? null,
          )
          setError('')
          setWorkspaceReady(true)
        }
      } catch (loadError) {
        console.error(loadError)
        if (!cancelled) {
          setError('Failed to load workspaces.')
          setWorkspaceReady(true)
        }
      }
    }

    void load()

    return () => {
      cancelled = true
    }
  }, [applyWorkspacePreset, currentWorkspaceId, setCurrentWorkspace, setError, setWorkspaces])

  return {
    workspaces,
    currentWorkspaceId,
    currentWorkspace,
    currentWorkspacePreset,
    currentWorkspacePanelSummary,
    workspaceNameMap,
    workspaceDeleteTargets,
    currentWorkspaceConnectorSummary,
    workspaceReady,
    creatingWorkspace,
    updatingWorkspace,
    deletingWorkspace,
    availableMcpConnectors,
    ...actions,
    ...forms,
  }
}

export type WorkspaceSidebarController = ReturnType<typeof useWorkspaceSidebarController>
