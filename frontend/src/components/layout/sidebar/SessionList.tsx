import type React from 'react'
import type { Session, Workspace } from '../../../api/client'
import { SessionItemRow, type SessionMetaPatch } from './SessionItemRow'

interface SessionListProps {
  sessions: Session[]
  emptyStateMessage: string
  currentSessionId: string | null
  editingSessionId: string | null
  editingTitle: string
  editingTags: string
  search: string
  movingSessionId: string | null
  savingId: string | null
  exportingId: string | null
  deletingId: string | null
  draggingSessionId: string | null
  dragOverSessionId: string | null
  hoveredId: string | null
  isMobile: boolean
  canDragSort: boolean
  workspaces: Workspace[]
  workspaceNameMap: Map<string, string>
  formatTime: (timestamp: number) => string
  onSelectSession: (session: Session) => void | Promise<void>
  onStartDraggingSession: (sessionId: string) => void
  onDragOverSession: (sessionId: string) => void
  onClearDragOver: () => void
  onDropSession: (sessionId: string) => void | Promise<void>
  onEndDragging: () => void
  onHoverSession: (sessionId: string | null) => void
  onEditingTitleChange: (value: string) => void
  onEditingTagsChange: (value: string) => void
  onEditKeyDown: (event: React.KeyboardEvent<HTMLInputElement>) => void
  onCancelEditing: () => void
  onSaveEditing: () => void | Promise<void>
  onPatchSession: (
    event: React.MouseEvent,
    sessionId: string,
    patch: SessionMetaPatch,
  ) => void | Promise<void>
  onToggleMoveSession: (sessionId: string) => void
  onStartEditing: (event: React.MouseEvent, session: Session) => void
  onExportSession: (event: React.MouseEvent, session: Session) => void | Promise<void>
  onDeleteSession: (event: React.MouseEvent, session: Session) => void | Promise<void>
  onMoveSession: (event: React.ChangeEvent<HTMLSelectElement>, session: Session) => void | Promise<void>
}

export function SessionList({
  sessions,
  emptyStateMessage,
  currentSessionId,
  editingSessionId,
  editingTitle,
  editingTags,
  search,
  movingSessionId,
  savingId,
  exportingId,
  deletingId,
  draggingSessionId,
  dragOverSessionId,
  hoveredId,
  isMobile,
  canDragSort,
  workspaces,
  workspaceNameMap,
  formatTime,
  onSelectSession,
  onStartDraggingSession,
  onDragOverSession,
  onClearDragOver,
  onDropSession,
  onEndDragging,
  onHoverSession,
  onEditingTitleChange,
  onEditingTagsChange,
  onEditKeyDown,
  onCancelEditing,
  onSaveEditing,
  onPatchSession,
  onToggleMoveSession,
  onStartEditing,
  onExportSession,
  onDeleteSession,
  onMoveSession,
}: SessionListProps) {
  if (sessions.length === 0) {
    return <div className="py-8 text-center text-xs text-text-secondary">{emptyStateMessage}</div>
  }

  return (
    <div className="space-y-1" data-testid="session-list">
      {sessions.map((session) => {
        const isActive = session.session_id === currentSessionId
        const isEditing = editingSessionId === session.session_id
        const showActions =
          isMobile ||
          isEditing ||
          movingSessionId === session.session_id ||
          hoveredId === session.session_id ||
          savingId === session.session_id ||
          exportingId === session.session_id ||
          deletingId === session.session_id ||
          isActive

        return (
          <SessionItemRow
            key={session.session_id}
            session={session}
            isActive={isActive}
            isEditing={isEditing}
            showActions={showActions}
            canDragSort={canDragSort}
            hasDraggingSession={Boolean(draggingSessionId)}
            isDragging={draggingSessionId === session.session_id}
            isDragOver={
              dragOverSessionId === session.session_id &&
              draggingSessionId !== session.session_id &&
              canDragSort
            }
            editingTitle={editingTitle}
            editingTags={editingTags}
            search={search}
            movingSessionId={movingSessionId}
            savingId={savingId}
            exportingId={exportingId}
            deletingId={deletingId}
            workspaces={workspaces}
            workspaceNameMap={workspaceNameMap}
            formatTime={formatTime}
            onSelectSession={onSelectSession}
            onStartDraggingSession={onStartDraggingSession}
            onDragOverSession={onDragOverSession}
            onClearDragOver={onClearDragOver}
            onDropSession={onDropSession}
            onEndDragging={onEndDragging}
            onHoverSession={onHoverSession}
            onEditingTitleChange={onEditingTitleChange}
            onEditingTagsChange={onEditingTagsChange}
            onEditKeyDown={onEditKeyDown}
            onCancelEditing={onCancelEditing}
            onSaveEditing={onSaveEditing}
            onPatchSession={onPatchSession}
            onToggleMoveSession={onToggleMoveSession}
            onStartEditing={onStartEditing}
            onExportSession={onExportSession}
            onDeleteSession={onDeleteSession}
            onMoveSession={onMoveSession}
          />
        )
      })}
    </div>
  )
}
