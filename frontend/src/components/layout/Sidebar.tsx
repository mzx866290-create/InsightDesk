import React, { useState } from 'react'
import {
  Plus,
  Settings,
} from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import { Button } from '../ui/Button'
import { BookmarkPanel } from './sidebar/BookmarkPanel'
import { SidebarCollapsedRail } from './sidebar/SidebarCollapsedRail'
import { SidebarHeader } from './sidebar/SidebarHeader'
import { SidebarSessionControls } from './sidebar/SidebarSessionControls'
import { SessionList } from './sidebar/SessionList'
import { WorkspaceSelector } from './sidebar/WorkspaceSelector'
import { useSessionSidebarController } from './sidebar/useSessionSidebarController'
import { useSidebarViewport } from './sidebar/useSidebarViewport'
import { useWorkspaceSidebarController } from './sidebar/useWorkspaceSidebarController'

export const Sidebar: React.FC = () => {
  const {
    sidebarOpen,
    panels: storePanels,
    webSearchEnabled,
    knowledgeBaseEnabled,
    enabledMcpServers,
    setSettingsOpen,
    toggleSidebar,
    setSidebarOpen,
  } = useChatStore()

  const [error, setError] = useState('')
  const [showBookmarks, setShowBookmarks] = useState(false)
  const isMobile = useSidebarViewport(setSidebarOpen)

  const workspaceController = useWorkspaceSidebarController({
    storePanels,
    webSearchEnabled,
    knowledgeBaseEnabled,
    enabledMcpServers,
    setError,
  })
  const {
    workspaces,
    workspaceNameMap,
    workspaceReady,
    syncWorkspaceForSession,
  } = workspaceController

  const {
    currentSessionId,
    loadingNew,
    deletingId,
    savingId,
    hoveredId,
    search,
    viewMode,
    editingSessionId,
    editingTitle,
    editingTags,
    movingSessionId,
    exportingId,
    draggingSessionId,
    dragOverSessionId,
    bookmarkSearch,
    removingBookmarkId,
    tagFilter,
    bookmarksCount,
    counts,
    allTags,
    filteredSessions,
    bookmarkGroups,
    canDragSort,
    emptyStateMessage,
    formatTime,
    handleNewChat,
    handleSelectSession,
    handleOpenBookmark,
    handleRemoveBookmark,
    handleExport,
    handleDelete,
    handleMoveSession,
    handleEditKeyDown,
    handleSessionDrop,
    applySessionPatch,
    startEditing,
    toggleMoveSession,
    cancelEditing,
    saveEditing,
    setSearch,
    setViewMode,
    setEditingTitle,
    setEditingTags,
    setHoveredId,
    setDraggingSessionId,
    setDragOverSessionId,
    setBookmarkSearch,
    setTagFilter,
    sendBookmarkToComposer,
  } = useSessionSidebarController({
    workspaceReady,
    showBookmarks,
    isMobile,
    syncWorkspaceForSession,
    setError,
  })

  const sidebarContent = (
    <>
      <SidebarHeader onToggleSidebar={toggleSidebar} />

      <div className="p-3">
        <WorkspaceSelector
          controller={workspaceController}
          storePanelCount={storePanels.length}
        />
        <Button
          variant="outline"
          data-testid="sidebar-new-chat"
          className="w-full justify-center gap-2 border-dashed border-bg-border hover:border-accent-blue/50 hover:bg-accent-blue/5"
          onClick={handleNewChat}
          loading={loadingNew}
        >
          <Plus size={15} />
          新建对话
        </Button>
      </div>

      <SidebarSessionControls
        search={search}
        showBookmarks={showBookmarks}
        bookmarkSearch={bookmarkSearch}
        bookmarksCount={bookmarksCount}
        counts={counts}
        viewMode={viewMode}
        allTags={allTags}
        tagFilter={tagFilter}
        canDragSort={canDragSort}
        filteredSessionCount={filteredSessions.length}
        error={error}
        onSearchChange={setSearch}
        onToggleBookmarks={() =>
          setShowBookmarks((current) => {
            if (current) {
              setBookmarkSearch('')
            }
            return !current
          })
        }
        onBookmarkSearchChange={setBookmarkSearch}
        onViewModeChange={setViewMode}
        onTagFilterChange={setTagFilter}
      />

      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {/* 书签视图 */}
        {showBookmarks && (
          <div className="mb-2">
            <BookmarkPanel
              bookmarksCount={bookmarksCount}
              groups={bookmarkGroups}
              removingBookmarkId={removingBookmarkId}
              formatTime={formatTime}
              onOpenBookmark={handleOpenBookmark}
              onRemoveBookmark={handleRemoveBookmark}
              onSendToComposer={sendBookmarkToComposer}
            />
          </div>
        )}

        {!showBookmarks && (
          <SessionList
            sessions={filteredSessions}
            emptyStateMessage={emptyStateMessage}
            currentSessionId={currentSessionId}
            editingSessionId={editingSessionId}
            editingTitle={editingTitle}
            editingTags={editingTags}
            search={search}
            movingSessionId={movingSessionId}
            savingId={savingId}
            exportingId={exportingId}
            deletingId={deletingId}
            draggingSessionId={draggingSessionId}
            dragOverSessionId={dragOverSessionId}
            hoveredId={hoveredId}
            isMobile={isMobile}
            canDragSort={canDragSort}
            workspaces={workspaces}
            workspaceNameMap={workspaceNameMap}
            formatTime={formatTime}
            onSelectSession={handleSelectSession}
            onStartDraggingSession={setDraggingSessionId}
            onDragOverSession={setDragOverSessionId}
            onClearDragOver={() => setDragOverSessionId(null)}
            onDropSession={handleSessionDrop}
            onEndDragging={() => {
              setDraggingSessionId(null)
              setDragOverSessionId(null)
            }}
            onHoverSession={setHoveredId}
            onEditingTitleChange={setEditingTitle}
            onEditingTagsChange={setEditingTags}
            onEditKeyDown={handleEditKeyDown}
            onCancelEditing={cancelEditing}
            onSaveEditing={saveEditing}
            onPatchSession={applySessionPatch}
            onToggleMoveSession={toggleMoveSession}
            onStartEditing={startEditing}
            onExportSession={handleExport}
            onDeleteSession={handleDelete}
            onMoveSession={handleMoveSession}
          />
        )}
      </div>

      <div className="border-t border-bg-border p-3">
        <button
          onClick={() => setSettingsOpen(true)}
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 pb-[calc(env(safe-area-inset-bottom)+0.625rem)] text-sm text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
        >
          <Settings size={15} />
          设置与上传
        </button>
      </div>
    </>
  )

  if (!sidebarOpen) {
    if (isMobile) {
      return null
    }

    return (
      <SidebarCollapsedRail
        onToggleSidebar={toggleSidebar}
        onNewChat={handleNewChat}
      />
    )
  }

  if (isMobile) {
    return (
      <>
        <button
          type="button"
          aria-label="Close sidebar overlay"
          onClick={toggleSidebar}
          className="fixed inset-0 z-30 bg-black/50 backdrop-blur-[1px]"
        />
        <aside className="fixed inset-y-0 left-0 z-40 flex w-[min(18rem,calc(100vw-1rem))] max-w-full flex-col border-r border-bg-border bg-bg-primary pb-[env(safe-area-inset-bottom)] shadow-2xl animate-slide-in">
          {sidebarContent}
        </aside>
      </>
    )
  }

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-bg-border bg-bg-primary animate-slide-in">
      {sidebarContent}
    </aside>
  )
}
