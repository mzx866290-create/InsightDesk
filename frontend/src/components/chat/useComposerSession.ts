import { createSession as apiCreateSession } from '../../api/client'
import type { Session } from '../../api/client'
import { useChatStore } from '../../stores/chatStore'

interface UseComposerSessionOptions {
  currentSessionId: string | null
  currentWorkspaceId: string | null
  setCurrentSession: (id: string | null) => void
  addSession: (session: Session) => void
  updateSession: (id: string, patch: Partial<Session>) => void
  adjustWorkspaceSessionCount: (workspaceId: string, delta: number) => void
}

export const useComposerSession = ({
  currentSessionId,
  currentWorkspaceId,
  setCurrentSession,
  addSession,
  updateSession,
  adjustWorkspaceSessionCount,
}: UseComposerSessionOptions) => {
  const syncSessionMetaFromPanels = (sessionId: string) => {
    const now = Date.now() / 1000
    const firstPanel = useChatStore.getState().panels[0]
    const messageCount = firstPanel
      ? firstPanel.messages.filter((message) => message.role !== 'error').length
      : 0

    updateSession(sessionId, {
      updated_at: now,
      message_count: messageCount,
    })
  }

  const ensureActiveSession = async (sessionTitleSeed: string): Promise<string | null> => {
    if (currentSessionId) return currentSessionId

    try {
      const session = await apiCreateSession(sessionTitleSeed.slice(0, 40), {
        workspace_id: currentWorkspaceId ?? undefined,
      })
      const nextSessionId = session.session_id
      const workspaceId = session.workspace_id ?? currentWorkspaceId ?? 'workspace-default'

      setCurrentSession(nextSessionId)
      addSession({
        session_id: nextSessionId,
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

      return nextSessionId
    } catch (error) {
      console.error('Failed to create session', error)
      return null
    }
  }

  return {
    ensureActiveSession,
    syncSessionMetaFromPanels,
  }
}
