import type React from 'react'
import {
  Archive,
  ArchiveRestore,
  Check,
  Download,
  FolderOpen,
  GripVertical,
  MessageSquare,
  Pencil,
  Pin,
  Star,
  Tag,
  Trash2,
  X,
} from 'lucide-react'
import type { Session, Workspace } from '../../../api/client'

export type SessionMetaPatch = Partial<Pick<Session, 'title' | 'tags' | 'is_pinned' | 'is_favorite' | 'is_archived'>>

interface SessionItemRowProps {
  session: Session
  isActive: boolean
  isEditing: boolean
  showActions: boolean
  canDragSort: boolean
  hasDraggingSession: boolean
  isDragging: boolean
  isDragOver: boolean
  editingTitle: string
  editingTags: string
  search: string
  movingSessionId: string | null
  savingId: string | null
  exportingId: string | null
  deletingId: string | null
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

export function SessionItemRow({
  session,
  isActive,
  isEditing,
  showActions,
  canDragSort,
  hasDraggingSession,
  isDragging,
  isDragOver,
  editingTitle,
  editingTags,
  search,
  movingSessionId,
  savingId,
  exportingId,
  deletingId,
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
}: SessionItemRowProps) {
  return (
    <div
      data-testid="session-item"
      data-session-id={session.session_id}
      className={`group cursor-pointer rounded-xl px-3 py-2.5 transition-colors ${
        isActive
          ? 'bg-accent-blue/15 text-text-primary'
          : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
      } ${isDragging ? 'opacity-60' : ''} ${
        isDragOver ? 'ring-1 ring-accent-blue/50' : ''
      }`}
      draggable={canDragSort && !isEditing}
      onClick={() => {
        if (!isEditing && !hasDraggingSession) {
          void onSelectSession(session)
        }
      }}
      onDragStart={(event) => {
        if (!canDragSort || isEditing) return
        onStartDraggingSession(session.session_id)
        event.dataTransfer.effectAllowed = 'move'
        event.dataTransfer.setData('text/plain', session.session_id)
      }}
      onDragOver={(event) => {
        if (!canDragSort || isEditing) return
        event.preventDefault()
        if (!isDragOver) {
          onDragOverSession(session.session_id)
        }
      }}
      onDragLeave={() => {
        if (isDragOver) {
          onClearDragOver()
        }
      }}
      onDrop={(event) => {
        if (!canDragSort || isEditing) return
        event.preventDefault()
        void onDropSession(session.session_id)
      }}
      onDragEnd={onEndDragging}
      onMouseEnter={() => onHoverSession(session.session_id)}
      onMouseLeave={() => onHoverSession(null)}
    >
      <div className="flex items-start gap-2">
        <MessageSquare
          size={14}
          className={`mt-0.5 shrink-0 ${isActive ? 'text-accent-blue' : ''}`}
        />
        <div className="min-w-0 flex-1">
          {isEditing ? (
            <div className="space-y-2" onClick={(event) => event.stopPropagation()}>
              <input
                value={editingTitle}
                onChange={(event) => onEditingTitleChange(event.target.value)}
                onKeyDown={onEditKeyDown}
                className="w-full rounded-lg border border-bg-border bg-bg-primary px-2.5 py-1.5 text-xs text-text-primary outline-none"
                placeholder="对话标题"
                autoFocus
              />
              <div className="flex items-start gap-2 rounded-lg border border-bg-border bg-bg-primary px-2.5 py-1.5">
                <Tag size={12} className="mt-0.5 shrink-0 text-text-secondary" />
                <input
                  value={editingTags}
                  onChange={(event) => onEditingTagsChange(event.target.value)}
                  onKeyDown={onEditKeyDown}
                  className="w-full bg-transparent text-[11px] text-text-primary outline-none placeholder:text-text-secondary"
                  placeholder="标签，用逗号分隔"
                />
              </div>
              <div className="flex items-center justify-end gap-1.5">
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation()
                    onCancelEditing()
                  }}
                  className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                  title="取消"
                >
                  <X size={13} />
                </button>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation()
                    void onSaveEditing()
                  }}
                  className="rounded-lg p-1.5 text-accent-blue transition-colors hover:bg-accent-blue/10"
                  title="保存"
                >
                  <Check size={13} />
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-1.5">
                {canDragSort && (
                  <GripVertical
                    size={11}
                    className="shrink-0 text-text-secondary/45"
                  />
                )}
                <div className="truncate text-xs font-medium">
                  {session.title || '新建对话'}
                </div>
                {session.is_pinned && (
                  <Pin size={11} className="shrink-0 fill-current text-accent-blue" />
                )}
                {session.is_favorite && (
                  <Star size={11} className="shrink-0 fill-current text-amber-300" />
                )}
                {session.is_archived && (
                  <span className="rounded-full border border-bg-border px-1.5 py-0.5 text-[9px] text-text-secondary">
                    已归档
                  </span>
                )}
              </div>
              <div className="mt-0.5 text-[10px] text-text-secondary/70">
                {formatTime(session.updated_at)} · {session.message_count} 条消息
              </div>
              {search.trim() && (
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  <span className="rounded-full bg-bg-secondary px-2 py-0.5 text-[10px] text-text-secondary">
                    {workspaceNameMap.get(session.workspace_id) ?? session.workspace_id}
                  </span>
                  {session.search_source === 'message' && session.search_preview && (
                    <span className="line-clamp-2 text-[10px] leading-relaxed text-text-secondary/80">
                      {session.search_preview}
                    </span>
                  )}
                </div>
              )}
              {session.tags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {session.tags.slice(0, 3).map((tag) => (
                    <span
                      key={`${session.session_id}-${tag}`}
                      className="rounded-full bg-bg-secondary px-2 py-0.5 text-[10px] text-text-secondary"
                    >
                      {tag}
                    </span>
                  ))}
                  {session.tags.length > 3 && (
                    <span className="rounded-full bg-bg-secondary px-2 py-0.5 text-[10px] text-text-secondary">
                      +{session.tags.length - 3}
                    </span>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {!isEditing && showActions && (
        <div className="mt-2 flex items-center justify-end gap-1">
          <button
            type="button"
            onClick={(event) => {
              void onPatchSession(event, session.session_id, {
                is_pinned: !session.is_pinned,
              })
            }}
            className={`rounded-lg p-1.5 transition-colors ${
              session.is_pinned
                ? 'text-accent-blue hover:bg-accent-blue/10'
                : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
            }`}
            disabled={savingId === session.session_id}
            title={session.is_pinned ? '取消置顶' : '置顶会话'}
          >
            <Pin size={12} className={session.is_pinned ? 'fill-current' : ''} />
          </button>
          <button
            type="button"
            onClick={(event) => {
              void onPatchSession(event, session.session_id, {
                is_favorite: !session.is_favorite,
              })
            }}
            className={`rounded-lg p-1.5 transition-colors ${
              session.is_favorite
                ? 'text-amber-300 hover:bg-amber-300/10'
                : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
            }`}
            disabled={savingId === session.session_id}
            title={session.is_favorite ? '取消收藏' : '收藏对话'}
          >
            <Star size={12} className={session.is_favorite ? 'fill-current' : ''} />
          </button>
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation()
              onToggleMoveSession(session.session_id)
            }}
            className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
            disabled={savingId === session.session_id}
            title="移动到工作区"
          >
            <FolderOpen size={12} />
          </button>
          <button
            type="button"
            onClick={(event) => onStartEditing(event, session)}
            className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
            disabled={savingId === session.session_id}
            title="重命名与编辑标签"
          >
            <Pencil size={12} />
          </button>
          <button
            type="button"
            onClick={(event) => {
              void onPatchSession(event, session.session_id, {
                is_archived: !session.is_archived,
              })
            }}
            className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
            disabled={savingId === session.session_id}
            title={session.is_archived ? '恢复对话' : '归档对话'}
          >
            {session.is_archived ? (
              <ArchiveRestore size={12} />
            ) : (
              <Archive size={12} />
            )}
          </button>
          <button
            type="button"
            onClick={(event) => void onExportSession(event, session)}
            className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
            disabled={exportingId === session.session_id}
            title="导出为 Markdown"
          >
            {exportingId === session.session_id ? (
              <span className="block h-3 w-3 rounded-full border border-current border-t-transparent animate-spin" />
            ) : (
              <Download size={12} />
            )}
          </button>
          <button
            onClick={(event) => onDeleteSession(event, session)}
            className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-accent-red/10 hover:text-accent-red"
            disabled={deletingId === session.session_id}
            title="删除对话"
          >
            {deletingId === session.session_id ? (
              <span className="block h-3 w-3 rounded-full border border-current border-t-transparent animate-spin" />
            ) : (
              <Trash2 size={12} />
            )}
          </button>
        </div>
      )}

      {movingSessionId === session.session_id && !isEditing && (
        <div
          className="mt-2 rounded-lg border border-bg-border bg-bg-primary p-2"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wide text-text-secondary">
            移动到工作区
          </div>
          <select
            value={session.workspace_id}
            onChange={(event) => {
              void onMoveSession(event, session)
            }}
            disabled={savingId === session.session_id}
            className="w-full rounded-lg border border-bg-border bg-bg-secondary px-2.5 py-2 text-[11px] text-text-primary outline-none disabled:cursor-not-allowed disabled:opacity-60"
          >
            {workspaces.map((workspace) => (
              <option key={workspace.workspace_id} value={workspace.workspace_id}>
                {workspace.name}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  )
}
