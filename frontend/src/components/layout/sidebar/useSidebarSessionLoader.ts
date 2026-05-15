import { useEffect } from 'react'
import { getSessions } from '../../../api/client'
import type { Session } from '../../../api/client'
import type { Panel } from '../../../stores/chatStoreModel'
import { DEMO_BACKEND_NOTICE } from '../../../utils/demoSession'

interface UseSidebarSessionLoaderOptions {
  workspaceReady: boolean
  currentWorkspaceId: string | null
  currentSessionId: string | null
  search: string
  storePanels: Panel[]
  setSessions: (sessions: Session[]) => void
  setCurrentSession: (sessionId: string | null) => void
  clearMessages: () => void
  clearWorkflow: (panelId: string) => void
  setError: (message: string) => void
}

export function useSidebarSessionLoader({
  workspaceReady,
  currentWorkspaceId,
  currentSessionId,
  search,
  storePanels,
  setSessions,
  setCurrentSession,
  clearMessages,
  clearWorkflow,
  setError,
}: UseSidebarSessionLoaderOptions) {
  useEffect(() => {
    if (!workspaceReady) return
    let cancelled = false

    const loadSessions = async () => {
      const normalizedSearch = search.trim()
      try {
        const nextSessions = await getSessions({
          query: normalizedSearch || undefined,
          workspace_id: normalizedSearch ? undefined : currentWorkspaceId ?? undefined,
        })
        if (cancelled) return

        setSessions(nextSessions)
        if (
          !normalizedSearch &&
          currentSessionId &&
          !nextSessions.some((session) => session.session_id === currentSessionId)
        ) {
          setCurrentSession(null)
          clearMessages()
          storePanels.forEach((panel) => clearWorkflow(panel.id))
        }
        setError('')
      } catch (loadError) {
        console.error(loadError)
        if (!cancelled) {
          setError(DEMO_BACKEND_NOTICE)
        }
      }
    }

    void loadSessions()

    return () => {
      cancelled = true
    }
  }, [
    clearMessages,
    clearWorkflow,
    currentSessionId,
    currentWorkspaceId,
    search,
    setCurrentSession,
    setError,
    setSessions,
    storePanels,
    workspaceReady,
  ])
}
