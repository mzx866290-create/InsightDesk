import { useState } from 'react'
import {
  createSession,
  getSessionMessages,
} from '../../../api/client'
import type { Session } from '../../../api/client'
import { useChatStore } from '../../../stores/chatStore'
import type { Panel } from '../../../stores/chatStoreModel'
import { useWorkflowStore } from '../../../stores/workflowStore'
import {
  createLocalDemoSession,
  DEMO_BACKEND_NOTICE,
} from '../../../utils/demoSession'
import {
  DEFAULT_WORKSPACE_ID,
  type SessionViewMode,
} from './sidebarConstants'
import {
  findLatestWorkflowNodes,
  mapMessages,
} from './sidebarModel'

interface UseSidebarSessionNavigationOptions {
  currentWorkspaceId: string | null
  currentSessionId: string | null
  storePanels: Panel[]
  search: string
  isMobile: boolean
  syncWorkspaceForSession: (session: Session, force?: boolean) => Promise<void>
  setSearch: (value: string) => void
  setViewMode: (mode: SessionViewMode) => void
  setTagFilter: (value: string | null) => void
  setMovingSessionId: (sessionId: string | null) => void
  setError: (message: string) => void
}

export function useSidebarSessionNavigation({
  currentWorkspaceId,
  currentSessionId,
  storePanels,
  search,
  isMobile,
  syncWorkspaceForSession,
  setSearch,
  setViewMode,
  setTagFilter,
  setMovingSessionId,
  setError,
}: UseSidebarSessionNavigationOptions) {
  const {
    addSession,
    updateSession,
    adjustWorkspaceSessionCount,
    setCurrentSession,
    clearMessages,
    loadMessagesToAllPanels,
    setPanels,
    setJumpTarget,
    setSidebarOpen,
  } = useChatStore()
  const hydrateWorkflow = useWorkflowStore((state) => state.hydrateWorkflow)
  const clearWorkflow = useWorkflowStore((state) => state.clearWorkflow)
  const [loadingNew, setLoadingNew] = useState(false)

  const resetPanelWorkflows = () => {
    storePanels.forEach((panel) => clearWorkflow(panel.id))
  }

  const handleNewChat = async () => {
    setLoadingNew(true)
    setMovingSessionId(null)
    try {
      const session = await createSession('新建对话', {
        workspace_id: currentWorkspaceId ?? undefined,
      })
      const workspaceId = session.workspace_id ?? currentWorkspaceId ?? DEFAULT_WORKSPACE_ID
      addSession({
        session_id: session.session_id,
        title: session.title,
        created_at: Date.now() / 1000,
        updated_at: Date.now() / 1000,
        message_count: 0,
        is_archived: false,
        is_favorite: false,
        is_pinned: false,
        session_order: 0,
        tags: [],
        workspace_id: workspaceId,
      })
      adjustWorkspaceSessionCount(workspaceId, 1)
      setCurrentSession(session.session_id)
      clearMessages()
      resetPanelWorkflows()
      setSearch('')
      setViewMode('all')
      setTagFilter(null)
      if (isMobile) {
        setSidebarOpen(false)
      }
      setError('')
    } catch (error) {
      console.error('Failed to create remote session; using local demo session.', error)
      const session = createLocalDemoSession(
        '新建对话',
        currentWorkspaceId ?? DEFAULT_WORKSPACE_ID,
      )
      addSession(session)
      adjustWorkspaceSessionCount(session.workspace_id, 1)
      setCurrentSession(session.session_id)
      clearMessages()
      resetPanelWorkflows()
      setSearch('')
      setViewMode('all')
      setTagFilter(null)
      setError(DEMO_BACKEND_NOTICE)
      if (isMobile) {
        setSidebarOpen(false)
      }
    } finally {
      setLoadingNew(false)
    }
  }

  const openSession = async (
    session: Session,
    options?: { forceWorkspaceSync?: boolean },
  ) => {
    const shouldSyncWorkspace =
      Boolean(options?.forceWorkspaceSync) || session.workspace_id !== currentWorkspaceId

    if (shouldSyncWorkspace) {
      await syncWorkspaceForSession(session, true)
    }

    setCurrentSession(session.session_id)
    try {
      const {
        messages,
        total_messages,
        panels: sessionPanels,
        panel_messages,
      } = await getSessionMessages(session.session_id)

      if (sessionPanels && sessionPanels.length > 0) {
        const nextPanelIds = new Set(sessionPanels.map((panel) => panel.panel_id))
        setPanels(
          sessionPanels.map((panel) => ({
            id: panel.panel_id,
            modelConfig: panel.model_config,
            messages: mapMessages(panel_messages?.[panel.panel_id] ?? messages),
          })),
        )
        sessionPanels.forEach((panel) => {
          const restoredMessages = panel_messages?.[panel.panel_id] ?? messages
          const workflowNodes = findLatestWorkflowNodes(restoredMessages)
          if (workflowNodes.length > 0) {
            hydrateWorkflow(panel.panel_id, workflowNodes)
          } else {
            clearWorkflow(panel.panel_id)
          }
        })
        storePanels.forEach((panel) => {
          if (!nextPanelIds.has(panel.id)) {
            clearWorkflow(panel.id)
          }
        })
      } else {
        loadMessagesToAllPanels(messages)
        const workflowNodes = findLatestWorkflowNodes(messages)
        storePanels.forEach((panel) => {
          if (workflowNodes.length > 0) {
            hydrateWorkflow(panel.id, workflowNodes)
          } else {
            clearWorkflow(panel.id)
          }
        })
      }

      updateSession(session.session_id, { message_count: total_messages })
      if (isMobile) {
        setSidebarOpen(false)
      }
    } catch (openError) {
      console.error(openError)
    }
  }

  const handleSelectSession = async (session: Session) => {
    const normalizedSearch = search.trim()
    const shouldJumpToSearchMatch =
      normalizedSearch.length > 0 && session.search_source === 'message'

    setMovingSessionId(null)

    if (shouldJumpToSearchMatch) {
      setJumpTarget({
        sessionId: session.session_id,
        role: 'assistant',
        searchQuery: normalizedSearch,
      })
    }

    if (session.session_id === currentSessionId) {
      if (isMobile) {
        setSidebarOpen(false)
      }
      return
    }

    await openSession(session, {
      forceWorkspaceSync: Boolean(normalizedSearch && session.workspace_id !== currentWorkspaceId),
    })
  }

  return {
    loadingNew,
    handleNewChat,
    handleSelectSession,
    openSession,
    resetPanelWorkflows,
  }
}
