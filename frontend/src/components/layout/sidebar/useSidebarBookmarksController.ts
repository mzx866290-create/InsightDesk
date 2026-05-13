import { useMemo, useState } from 'react'
import {
  deleteBookmark as deleteBookmarkRequest,
  getSessions,
} from '../../../api/client'
import type { Bookmark as StoredBookmark, Session } from '../../../api/client'
import { useChatStore } from '../../../stores/chatStore'
import {
  buildBookmarkGroups,
  filterBookmarksByKeyword,
} from './sidebarModel'

interface UseSidebarBookmarksControllerOptions {
  sessions: Session[]
  currentSessionId: string | null
  isMobile: boolean
  onBeforeOpenBookmark: () => void
  openSession: (session: Session, options?: { forceWorkspaceSync?: boolean }) => Promise<void>
  setError: (message: string) => void
}

export function useSidebarBookmarksController({
  sessions,
  currentSessionId,
  isMobile,
  onBeforeOpenBookmark,
  openSession,
  setError,
}: UseSidebarBookmarksControllerOptions) {
  const bookmarks = useChatStore((state) => state.bookmarks)
  const removeBookmark = useChatStore((state) => state.removeBookmark)
  const pushComposerSeed = useChatStore((state) => state.pushComposerSeed)
  const setJumpTarget = useChatStore((state) => state.setJumpTarget)
  const setSidebarOpen = useChatStore((state) => state.setSidebarOpen)

  const [bookmarkSearch, setBookmarkSearch] = useState('')
  const [removingBookmarkId, setRemovingBookmarkId] = useState<string | null>(null)

  const filteredBookmarks = useMemo(() => {
    return filterBookmarksByKeyword(bookmarks, bookmarkSearch)
  }, [bookmarkSearch, bookmarks])
  const bookmarkGroups = useMemo(
    () => buildBookmarkGroups(filteredBookmarks),
    [filteredBookmarks],
  )

  const handleOpenBookmark = async (bookmark: StoredBookmark) => {
    if (!bookmark.sessionId) return

    onBeforeOpenBookmark()
    setJumpTarget({
      sessionId: bookmark.sessionId,
      role: bookmark.role,
      panelId: bookmark.panelId || undefined,
      answerGroupId: bookmark.answerGroupId || undefined,
      messageId: bookmark.messageId,
    })

    if (bookmark.sessionId === currentSessionId) {
      if (isMobile) {
        setSidebarOpen(false)
      }
      return
    }

    let targetSession =
      sessions.find((session) => session.session_id === bookmark.sessionId) ?? null

    if (!targetSession) {
      try {
        const allSessions = await getSessions()
        targetSession =
          allSessions.find((session) => session.session_id === bookmark.sessionId) ?? null
      } catch (sessionError) {
        console.error(sessionError)
      }
    }

    if (!targetSession) {
      setError('Bookmark session not found.')
      return
    }

    await openSession(targetSession, { forceWorkspaceSync: true })
  }

  const handleRemoveBookmark = async (
    bookmarkId: string,
    source: 'remote' | 'local' = 'remote',
  ) => {
    setRemovingBookmarkId(bookmarkId)
    setError('')
    try {
      if (source === 'remote') {
        await deleteBookmarkRequest(bookmarkId)
      }
      removeBookmark(bookmarkId)
    } catch (bookmarkError) {
      console.error(bookmarkError)
      setError((bookmarkError as Error).message ?? 'Failed to remove bookmark.')
    } finally {
      setRemovingBookmarkId(null)
    }
  }

  const removeBookmarksForSession = (sessionId: string) => {
    bookmarks
      .filter((bookmark) => bookmark.sessionId === sessionId)
      .forEach((bookmark) => removeBookmark(bookmark.id))
  }

  return {
    bookmarkSearch,
    removingBookmarkId,
    bookmarksCount: bookmarks.length,
    bookmarkGroups,
    handleOpenBookmark,
    handleRemoveBookmark,
    removeBookmarksForSession,
    setBookmarkSearch,
    sendBookmarkToComposer: (content: string) => pushComposerSeed({ text: content }),
  }
}
