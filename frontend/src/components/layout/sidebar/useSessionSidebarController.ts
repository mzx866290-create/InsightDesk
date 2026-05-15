import type { KeyboardEvent } from 'react'
import { useState } from 'react'
import type { Session } from '../../../api/client'
import { useChatStore } from '../../../stores/chatStore'
import { useWorkflowStore } from '../../../stores/workflowStore'
import { formatSessionTimestamp } from './sidebarModel'
import { useSidebarBookmarksController } from './useSidebarBookmarksController'
import { useSidebarSessionEditing } from './useSidebarSessionEditing'
import { useSidebarSessionFilters } from './useSidebarSessionFilters'
import { useSidebarSessionLoader } from './useSidebarSessionLoader'
import { useSidebarSessionMutations } from './useSidebarSessionMutations'
import { useSidebarSessionNavigation } from './useSidebarSessionNavigation'
import { useSidebarSessionReorder } from './useSidebarSessionReorder'

interface UseSessionSidebarControllerOptions {
  workspaceReady: boolean
  showBookmarks: boolean
  isMobile: boolean
  syncWorkspaceForSession: (session: Session, force?: boolean) => Promise<void>
  setError: (message: string) => void
}

export function useSessionSidebarController({
  workspaceReady,
  showBookmarks,
  isMobile,
  syncWorkspaceForSession,
  setError,
}: UseSessionSidebarControllerOptions) {
  const {
    sessions,
    currentSessionId,
    currentWorkspaceId,
    panels: storePanels,
    setSessions,
    setCurrentSession,
    clearMessages,
  } = useChatStore()
  const clearWorkflow = useWorkflowStore((state) => state.clearWorkflow)

  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [movingSessionId, setMovingSessionId] = useState<string | null>(null)
  const filters = useSidebarSessionFilters({ sessions })
  const editingController = useSidebarSessionEditing({
    setMovingSessionId,
    setError,
  })

  useSidebarSessionLoader({
    workspaceReady,
    currentWorkspaceId,
    currentSessionId,
    search: filters.search,
    storePanels,
    setSessions,
    setCurrentSession,
    clearMessages,
    clearWorkflow,
    setError,
  })

  const {
    loadingNew,
    handleNewChat,
    handleSelectSession,
    openSession,
    resetPanelWorkflows,
  } = useSidebarSessionNavigation({
    currentWorkspaceId,
    currentSessionId,
    storePanels,
    search: filters.search,
    isMobile,
    syncWorkspaceForSession,
    setSearch: filters.setSearch,
    setViewMode: filters.setViewMode,
    setTagFilter: filters.setTagFilter,
    setMovingSessionId,
    setError,
  })

  const bookmarkController = useSidebarBookmarksController({
    sessions,
    currentSessionId,
    isMobile,
    onBeforeOpenBookmark: () => setMovingSessionId(null),
    openSession,
    setError,
  })

  const {
    deletingId,
    savingId,
    exportingId,
    handleExport,
    handleDelete,
    handleMoveSession,
    applySessionPatch,
  } = useSidebarSessionMutations({
    currentSessionId,
    currentWorkspaceId,
    editingSessionId: editingController.editingSessionId,
    viewMode: filters.viewMode,
    cancelEditing: editingController.cancelEditing,
    removeBookmarksForSession: bookmarkController.removeBookmarksForSession,
    resetPanelWorkflows,
    setMovingSessionId,
    setViewMode: filters.setViewMode,
    setError,
  })

  const toggleMoveSession = (sessionId: string) => {
    setMovingSessionId((current) =>
      current === sessionId ? null : sessionId,
    )
    editingController.cancelEditing()
    setError('')
  }

  const saveEditing = async () => {
    await editingController.saveEditing(applySessionPatch)
  }

  const handleEditKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    editingController.handleEditKeyDown(event, () => void saveEditing())
  }

  const reorderController = useSidebarSessionReorder({
    sessions,
    filteredSessions: filters.filteredSessions,
    currentWorkspaceId,
    search: filters.search,
    showBookmarks,
    viewMode: filters.viewMode,
    setSessions,
    setError,
  })

  return {
    sessions,
    currentSessionId,
    loadingNew,
    deletingId,
    savingId,
    hoveredId,
    search: filters.search,
    viewMode: filters.viewMode,
    editingSessionId: editingController.editingSessionId,
    editingTitle: editingController.editingTitle,
    editingTags: editingController.editingTags,
    movingSessionId,
    exportingId,
    draggingSessionId: reorderController.draggingSessionId,
    dragOverSessionId: reorderController.dragOverSessionId,
    bookmarkSearch: bookmarkController.bookmarkSearch,
    removingBookmarkId: bookmarkController.removingBookmarkId,
    tagFilter: filters.tagFilter,
    bookmarksCount: bookmarkController.bookmarksCount,
    counts: filters.counts,
    allTags: filters.allTags,
    filteredSessions: filters.filteredSessions,
    bookmarkGroups: bookmarkController.bookmarkGroups,
    canDragSort: reorderController.canDragSort,
    emptyStateMessage: filters.emptyStateMessage,
    formatTime: formatSessionTimestamp,
    handleNewChat,
    handleSelectSession,
    handleOpenBookmark: bookmarkController.handleOpenBookmark,
    handleRemoveBookmark: bookmarkController.handleRemoveBookmark,
    handleExport,
    handleDelete,
    handleMoveSession,
    handleEditKeyDown,
    handleSessionDrop: reorderController.handleSessionDrop,
    applySessionPatch,
    startEditing: editingController.startEditing,
    toggleMoveSession,
    cancelEditing: editingController.cancelEditing,
    saveEditing,
    setSearch: filters.setSearch,
    setViewMode: filters.setViewMode,
    setEditingTitle: editingController.setEditingTitle,
    setEditingTags: editingController.setEditingTags,
    setHoveredId,
    setDraggingSessionId: reorderController.setDraggingSessionId,
    setDragOverSessionId: reorderController.setDragOverSessionId,
    setBookmarkSearch: bookmarkController.setBookmarkSearch,
    setTagFilter: filters.setTagFilter,
    sendBookmarkToComposer: bookmarkController.sendBookmarkToComposer,
  }
}
