import type { Bookmark as StoredBookmark, Message, Session } from '../../../api/client'
import type { SessionViewMode } from './sidebarConstants'

export interface BookmarkGroup {
  key: string
  title: string
  updatedAt: number
  items: StoredBookmark[]
}

export interface SessionModeCounts {
  all: number
  favorite: number
  archived: number
}

export function mapMessages(messages: Message[]) {
  return messages.map((message, index) => ({
    id: `loaded-${index}`,
    role: message.role,
    content: message.content,
    images: message.images,
    files: message.files,
    sources: message.sources,
    modelId: message.model_id,
    answerGroupId: message.answer_group_id,
    taskId: message.task_id,
    taskType: message.task_type,
    workflowNodes: message.workflow_nodes,
    tokenUsage: message.token_usage,
  }))
}

export function findLatestWorkflowNodes(
  messages: Message[],
): NonNullable<Message['workflow_nodes']> {
  const latestAssistantMessage = [...messages]
    .reverse()
    .find(
      (message) =>
        message.role === 'assistant' && (message.workflow_nodes?.length ?? 0) > 0,
    )

  return latestAssistantMessage?.workflow_nodes ?? []
}

export function countSessionsByView(sessions: Session[]): SessionModeCounts {
  return {
    all: sessions.filter((session) => !session.is_archived).length,
    favorite: sessions.filter((session) => session.is_favorite && !session.is_archived).length,
    archived: sessions.filter((session) => session.is_archived).length,
  }
}

export function collectSessionTags(sessions: Session[], limit = 12): string[] {
  const tagSet = new Set<string>()
  sessions.forEach((session) => session.tags.forEach((tag) => tagSet.add(tag)))
  return Array.from(tagSet).slice(0, limit)
}

export function filterSessionsByView(
  sessions: Session[],
  viewMode: SessionViewMode,
  tagFilter: string | null,
): Session[] {
  return sessions.filter((session) => {
    if (viewMode === 'all' && session.is_archived) return false
    if (viewMode === 'favorite' && (!session.is_favorite || session.is_archived)) return false
    if (viewMode === 'archived' && !session.is_archived) return false
    if (tagFilter && !session.tags.includes(tagFilter)) return false
    return true
  })
}

export function parseSessionTagDraft(value: string): string[] {
  return value
    .split(/[\n,，]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

export function formatSessionTimestamp(ts: number, now = new Date()): string {
  const date = new Date(ts * 1000)
  const diff = now.getTime() - date.getTime()
  if (diff < 86400000) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

export function getSessionEmptyStateMessage(
  search: string,
  viewMode: SessionViewMode,
): string {
  if (search.trim()) return 'No matching cross-session results.'
  if (viewMode === 'favorite') return 'No favorite sessions yet.'
  if (viewMode === 'archived') return 'No archived sessions.'
  return '暂无对话记录'
}

export function canDragSortSessions({
  search,
  showBookmarks,
  viewMode,
  reorderingSessions,
}: {
  search: string
  showBookmarks: boolean
  viewMode: SessionViewMode
  reorderingSessions: boolean
}): boolean {
  return !search.trim() && !showBookmarks && viewMode === 'all' && !reorderingSessions
}

export function buildReorderedSessionIds(
  visibleSessions: Session[],
  draggingSessionId: string | null,
  targetSessionId: string,
): string[] | null {
  if (!draggingSessionId || draggingSessionId === targetSessionId) return null

  const currentOrder = visibleSessions.map((session) => session.session_id)
  const sourceIndex = currentOrder.indexOf(draggingSessionId)
  const targetIndex = currentOrder.indexOf(targetSessionId)
  if (sourceIndex < 0 || targetIndex < 0 || sourceIndex === targetIndex) return null

  const nextOrder = [...currentOrder]
  const [movedSessionId] = nextOrder.splice(sourceIndex, 1)
  nextOrder.splice(targetIndex, 0, movedSessionId)
  return nextOrder
}

export function applyOptimisticSessionOrder(
  sessions: Session[],
  orderedSessionIds: string[],
): Session[] {
  const orderSize = orderedSessionIds.length
  const orderMap = new Map(
    orderedSessionIds.map((sessionId, index) => [sessionId, orderSize - index]),
  )

  return sessions.map((session) => {
    const order = orderMap.get(session.session_id)
    if (order === undefined) return session
    return {
      ...session,
      session_order: order,
    }
  })
}

export function filterBookmarksByKeyword(
  bookmarks: StoredBookmark[],
  search: string,
): StoredBookmark[] {
  const keyword = search.trim().toLowerCase()
  if (!keyword) return bookmarks

  return bookmarks.filter((bookmark) =>
    [
      bookmark.sessionTitle,
      bookmark.content,
      bookmark.modelId ?? '',
    ].some((value) => value.toLowerCase().includes(keyword)),
  )
}

export function buildBookmarkGroups(bookmarks: StoredBookmark[]): BookmarkGroup[] {
  const groups = new Map<string, BookmarkGroup>()

  bookmarks.forEach((bookmark) => {
    const title = bookmark.sessionTitle.trim() || 'Untitled session'
    const key = bookmark.sessionId || `session-title:${title}`
    const updatedAt = bookmark.updatedAt || bookmark.createdAt || 0
    const existing = groups.get(key)

    if (existing) {
      existing.items.push(bookmark)
      existing.updatedAt = Math.max(existing.updatedAt, updatedAt)
      return
    }

    groups.set(key, {
      key,
      title,
      updatedAt,
      items: [bookmark],
    })
  })

  return [...groups.values()]
    .map((group) => ({
      ...group,
      items: [...group.items].sort(
        (a, b) => (b.updatedAt || b.createdAt || 0) - (a.updatedAt || a.createdAt || 0),
      ),
    }))
    .sort((a, b) => b.updatedAt - a.updatedAt)
}
