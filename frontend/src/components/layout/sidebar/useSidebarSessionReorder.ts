import { useState } from 'react'
import {
  getSessions,
  reorderSessions,
} from '../../../api/client'
import type { Session } from '../../../api/client'
import {
  applyOptimisticSessionOrder,
  buildReorderedSessionIds,
  canDragSortSessions,
} from './sidebarModel'
import type { SessionViewMode } from './sidebarConstants'

interface UseSidebarSessionReorderOptions {
  sessions: Session[]
  filteredSessions: Session[]
  currentWorkspaceId: string | null
  search: string
  showBookmarks: boolean
  viewMode: SessionViewMode
  setSessions: (sessions: Session[]) => void
  setError: (message: string) => void
}

export function useSidebarSessionReorder({
  sessions,
  filteredSessions,
  currentWorkspaceId,
  search,
  showBookmarks,
  viewMode,
  setSessions,
  setError,
}: UseSidebarSessionReorderOptions) {
  const [draggingSessionId, setDraggingSessionId] = useState<string | null>(null)
  const [dragOverSessionId, setDragOverSessionId] = useState<string | null>(null)
  const [reorderingSessions, setReorderingSessions] = useState(false)

  const canDragSort = canDragSortSessions({
    search,
    showBookmarks,
    viewMode,
    reorderingSessions,
  })

  const handleSessionDrop = async (targetSessionId: string) => {
    if (!canDragSort) return

    const nextOrder = buildReorderedSessionIds(
      filteredSessions,
      draggingSessionId,
      targetSessionId,
    )
    if (!nextOrder) return

    setSessions(applyOptimisticSessionOrder(sessions, nextOrder))
    setReorderingSessions(true)
    setError('')
    try {
      const orderedSessions = await reorderSessions(nextOrder, {
        workspace_id: currentWorkspaceId ?? undefined,
      })
      setSessions(orderedSessions)
    } catch (reorderError) {
      console.error(reorderError)
      setError((reorderError as Error).message ?? 'Failed to reorder sessions.')
      try {
        const fallbackSessions = await getSessions({
          workspace_id: currentWorkspaceId ?? undefined,
        })
        setSessions(fallbackSessions)
      } catch (reloadError) {
        console.error(reloadError)
      }
    } finally {
      setReorderingSessions(false)
      setDraggingSessionId(null)
      setDragOverSessionId(null)
    }
  }

  return {
    draggingSessionId,
    dragOverSessionId,
    canDragSort,
    handleSessionDrop,
    setDraggingSessionId,
    setDragOverSessionId,
  }
}
