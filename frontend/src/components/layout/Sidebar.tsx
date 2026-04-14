import React, { useEffect, useMemo, useState } from 'react'
import {
  Plus,
  MessageSquare,
  Trash2,
  Settings,
  ChevronLeft,
  Brain,
  Search,
  Star,
  GripVertical,
  Pin,
  Archive,
  ArchiveRestore,
  Pencil,
  Check,
  X,
  Tag,
  FolderOpen,
  Download,
  Bookmark,
} from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import { useWorkflowStore } from '../../stores/workflowStore'
import {
  activateWorkspace,
  getSessions,
  getWorkspaces,
  createSession,
  createWorkspace,
  deleteBookmark as deleteBookmarkRequest,
  deleteWorkspace as deleteWorkspaceRequest,
  deleteSession,
  getSessionMessages,
  reorderSessions,
  updateSessionMeta,
  updateWorkspace as updateWorkspaceRequest,
} from '../../api/client'
import type { Bookmark as StoredBookmark, Message, Session, Workspace } from '../../api/client'
import { Button } from '../ui/Button'

function mapMessages(messages: Message[]) {
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
  }))
}

function findLatestWorkflowNodes(messages: Message[]) {
  const latestAssistantMessage = [...messages]
    .reverse()
    .find(
      (message) =>
        message.role === 'assistant' && (message.workflow_nodes?.length ?? 0) > 0,
    )

  return latestAssistantMessage?.workflow_nodes ?? []
}

type SessionViewMode = 'all' | 'favorite' | 'archived'
const DEFAULT_WORKSPACE_ID = 'workspace-default'

const WORKSPACE_COLOR_TONES: Record<Workspace['color'], string> = {
  blue: 'bg-accent-blue/15 text-accent-blue',
  green: 'bg-accent-green/15 text-accent-green',
  amber: 'bg-amber-300/15 text-amber-300',
  rose: 'bg-rose-400/15 text-rose-300',
  slate: 'bg-slate-400/15 text-slate-300',
}

const WORKSPACE_COLOR_LABELS: Record<Workspace['color'], string> = {
  blue: '蓝色',
  green: '绿色',
  amber: '琥珀',
  rose: '玫瑰',
  slate: '石板',
}

interface BookmarkGroup {
  key: string
  title: string
  updatedAt: number
  items: StoredBookmark[]
}

export const Sidebar: React.FC = () => {
  const {
    workspaces,
    currentWorkspaceId,
    sessions,
    currentSessionId,
    sidebarOpen,
    panels: storePanels,
    setWorkspaces,
    setCurrentWorkspace,
    setSessions,
    setCurrentSession,
    addSession,
    removeSession,
    updateSession,
    updateWorkspace: updateWorkspaceInStore,
    adjustWorkspaceSessionCount,
    clearMessages,
    loadMessagesToAllPanels,
    setPanels,
    setSettingsOpen,
    setJumpTarget,
    toggleSidebar,
    setSidebarOpen,
  } = useChatStore()
  const hydrateWorkflow = useWorkflowStore((s) => s.hydrateWorkflow)
  const clearWorkflow = useWorkflowStore((s) => s.clearWorkflow)

  const [loadingNew, setLoadingNew] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [viewMode, setViewMode] = useState<SessionViewMode>('all')
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState('')
  const [editingTags, setEditingTags] = useState('')
  const [error, setError] = useState('')
  const [workspaceReady, setWorkspaceReady] = useState(false)
  const [creatingWorkspace, setCreatingWorkspace] = useState(false)
  const [updatingWorkspace, setUpdatingWorkspace] = useState(false)
  const [deletingWorkspace, setDeletingWorkspace] = useState(false)
  const [showWorkspaceForm, setShowWorkspaceForm] = useState(false)
  const [showWorkspaceEditForm, setShowWorkspaceEditForm] = useState(false)
  const [showWorkspaceDeleteForm, setShowWorkspaceDeleteForm] = useState(false)
  const [workspaceName, setWorkspaceName] = useState('')
  const [workspaceColor, setWorkspaceColor] = useState<Workspace['color']>('blue')
  const [workspaceEditName, setWorkspaceEditName] = useState('')
  const [workspaceEditDescription, setWorkspaceEditDescription] = useState('')
  const [workspaceEditColor, setWorkspaceEditColor] = useState<Workspace['color']>('blue')
  const [workspaceDeleteTargetId, setWorkspaceDeleteTargetId] = useState(DEFAULT_WORKSPACE_ID)
  const [movingSessionId, setMovingSessionId] = useState<string | null>(null)
  const [exportingId, setExportingId] = useState<string | null>(null)
  const [draggingSessionId, setDraggingSessionId] = useState<string | null>(null)
  const [dragOverSessionId, setDragOverSessionId] = useState<string | null>(null)
  const [reorderingSessions, setReorderingSessions] = useState(false)
  const [showBookmarks, setShowBookmarks] = useState(false)
  const [bookmarkSearch, setBookmarkSearch] = useState('')
  const [removingBookmarkId, setRemovingBookmarkId] = useState<string | null>(null)
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768)
  const [tagFilter, setTagFilter] = useState<string | null>(null)
  const bookmarks = useChatStore((s) => s.bookmarks)
  const removeBookmark = useChatStore((s) => s.removeBookmark)
  const pushComposerSeed = useChatStore((s) => s.pushComposerSeed)

  const currentWorkspace = useMemo(
    () =>
      workspaces.find((workspace) => workspace.workspace_id === currentWorkspaceId) ?? null,
    [currentWorkspaceId, workspaces],
  )
  const workspaceNameMap = useMemo(
    () => new Map(workspaces.map((workspace) => [workspace.workspace_id, workspace.name])),
    [workspaces],
  )
  const workspaceDeleteTargets = useMemo(
    () =>
      workspaces.filter((workspace) => workspace.workspace_id !== currentWorkspace?.workspace_id),
    [currentWorkspace?.workspace_id, workspaces],
  )

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      try {
        const payload = await getWorkspaces()
        if (!cancelled) {
          setWorkspaces(payload.workspaces)
          const nextWorkspaceId =
            currentWorkspaceId && payload.workspaces.some((item) => item.workspace_id === currentWorkspaceId)
              ? currentWorkspaceId
              : payload.active_workspace_id ?? payload.workspaces[0]?.workspace_id ?? null
          setCurrentWorkspace(nextWorkspaceId)
          setError('')
          setWorkspaceReady(true)
        }
      } catch (loadError) {
        console.error(loadError)
        if (!cancelled) {
          setError('加载工作区失败。')
          setWorkspaceReady(true)
        }
      }
    }

    void load()

    return () => {
      cancelled = true
    }
  }, [currentWorkspaceId, setCurrentWorkspace, setWorkspaces])

  useEffect(() => {
    if (!workspaceReady) return
    let cancelled = false

    const load = async () => {
      const normalizedSearch = search.trim()
      try {
        const nextSessions = await getSessions({
          query: normalizedSearch || undefined,
          workspace_id: normalizedSearch ? undefined : currentWorkspaceId ?? undefined,
        })
        if (!cancelled) {
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
        }
      } catch (loadError) {
        console.error(loadError)
        if (!cancelled) {
          setError('加载对话历史失败。')
        }
      }
    }

    void load()

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
    setSessions,
    storePanels,
    workspaceReady,
  ])

  useEffect(() => {
    const media = window.matchMedia('(max-width: 767px)')

    const applyViewport = (matches: boolean) => {
      setIsMobile(matches)
      if (matches) {
        setSidebarOpen(false)
      }
    }

    applyViewport(media.matches)

    const handleChange = (event: MediaQueryListEvent) => {
      applyViewport(event.matches)
    }

    media.addEventListener('change', handleChange)
    return () => media.removeEventListener('change', handleChange)
  }, [setSidebarOpen])

  const handleNewChat = async () => {
    setLoadingNew(true)
    setMovingSessionId(null)
    try {
      const s = await createSession('新建对话', {
        workspace_id: currentWorkspaceId ?? undefined,
      })
      addSession({
        session_id: s.session_id,
        title: s.title,
        created_at: Date.now() / 1000,
        updated_at: Date.now() / 1000,
        message_count: 0,
        is_archived: false,
        is_favorite: false,
        is_pinned: false,
        session_order: 0,
        tags: [],
        workspace_id: s.workspace_id ?? currentWorkspaceId ?? 'workspace-default',
      })
      adjustWorkspaceSessionCount(
        s.workspace_id ?? currentWorkspaceId ?? 'workspace-default',
        1,
      )
      setCurrentSession(s.session_id)
      clearMessages()
      storePanels.forEach((panel) => clearWorkflow(panel.id))
      setSearch('')
      setViewMode('all')
      setTagFilter(null)
      if (isMobile) {
        setSidebarOpen(false)
      }
    } finally {
      setLoadingNew(false)
    }
  }

  const handleSelectWorkspace = async (workspaceId: string) => {
    if (!workspaceId || workspaceId === currentWorkspaceId) return
    setError('')
    setShowWorkspaceEditForm(false)
    setShowWorkspaceDeleteForm(false)
    try {
      const activated = await activateWorkspace(workspaceId)
      setCurrentWorkspace(activated.workspace_id)
      setWorkspaces(
        workspaces.map((workspace) =>
          workspace.workspace_id === activated.workspace_id
            ? activated
            : { ...workspace, is_active: false },
        ),
      )
    } catch (workspaceError) {
      console.error(workspaceError)
      setError((workspaceError as Error).message ?? '切换工作区失败。')
    }
  }

  const handleCreateWorkspace = async () => {
    const name = workspaceName.trim()
    if (!name) {
      setError('工作区名称不能为空。')
      return
    }
    setCreatingWorkspace(true)
    setError('')
    try {
      const workspace = await createWorkspace({
        name,
        color: workspaceColor,
        activate: true,
      })
      setWorkspaces(
        [
          workspace,
          ...workspaces.filter((item) => item.workspace_id !== workspace.workspace_id).map((item) => ({
            ...item,
            is_active: false,
          })),
        ],
      )
      setCurrentWorkspace(workspace.workspace_id)
      setWorkspaceName('')
      setWorkspaceColor('blue')
      setShowWorkspaceForm(false)
      setShowWorkspaceEditForm(false)
      setShowWorkspaceDeleteForm(false)
    } catch (workspaceError) {
      console.error(workspaceError)
      setError((workspaceError as Error).message ?? '创建工作区失败。')
    } finally {
      setCreatingWorkspace(false)
    }
  }

  const openWorkspaceEditor = () => {
    if (!currentWorkspace) return
    setWorkspaceEditName(currentWorkspace.name)
    setWorkspaceEditDescription(currentWorkspace.description)
    setWorkspaceEditColor(currentWorkspace.color)
    setShowWorkspaceEditForm(true)
    setShowWorkspaceForm(false)
    setShowWorkspaceDeleteForm(false)
    setError('')
  }

  const cancelWorkspaceEditor = () => {
    setShowWorkspaceEditForm(false)
    setWorkspaceEditName('')
    setWorkspaceEditDescription('')
    setWorkspaceEditColor('blue')
  }

  const openWorkspaceDeletePrompt = () => {
    if (!currentWorkspace || currentWorkspace.workspace_id === DEFAULT_WORKSPACE_ID) return
    setWorkspaceDeleteTargetId(workspaceDeleteTargets[0]?.workspace_id ?? DEFAULT_WORKSPACE_ID)
    setShowWorkspaceDeleteForm(true)
    setShowWorkspaceEditForm(false)
    setShowWorkspaceForm(false)
    setError('')
  }

  const cancelWorkspaceDelete = () => {
    setShowWorkspaceDeleteForm(false)
    setWorkspaceDeleteTargetId(DEFAULT_WORKSPACE_ID)
  }

  const handleUpdateWorkspace = async () => {
    if (!currentWorkspace) return
    const name = workspaceEditName.trim()
    if (!name) {
      setError('工作区名称不能为空。')
      return
    }

    setUpdatingWorkspace(true)
    setError('')
    try {
      const updated = await updateWorkspaceRequest(currentWorkspace.workspace_id, {
        name,
        description: workspaceEditDescription.trim(),
        color: workspaceEditColor,
      })
      updateWorkspaceInStore(updated.workspace_id, updated)
      cancelWorkspaceEditor()
    } catch (workspaceError) {
      console.error(workspaceError)
      setError((workspaceError as Error).message ?? '更新工作区失败。')
    } finally {
      setUpdatingWorkspace(false)
    }
  }

  const handleDeleteWorkspace = async () => {
    if (!currentWorkspace || currentWorkspace.workspace_id === DEFAULT_WORKSPACE_ID) return

    const targetWorkspaceId =
      workspaceDeleteTargetId.trim() ||
      workspaceDeleteTargets[0]?.workspace_id ||
      DEFAULT_WORKSPACE_ID

    setDeletingWorkspace(true)
    setError('')
    try {
      const result = await deleteWorkspaceRequest(currentWorkspace.workspace_id, {
        target_workspace_id: targetWorkspaceId,
      })
      const payload = await getWorkspaces()
      setWorkspaces(payload.workspaces)
      setCurrentWorkspace(result.target_workspace_id)
      cancelWorkspaceDelete()
      cancelWorkspaceEditor()
    } catch (workspaceError) {
      console.error(workspaceError)
      setError((workspaceError as Error).message ?? '删除工作区失败。')
    } finally {
      setDeletingWorkspace(false)
    }
  }

  const syncWorkspaceForSession = async (session: Session, force = false) => {
    if (!force && session.workspace_id === currentWorkspaceId) return
    if (session.workspace_id === currentWorkspaceId) return
    try {
      const activated = await activateWorkspace(session.workspace_id)
      setCurrentWorkspace(activated.workspace_id)
      setWorkspaces(
        workspaces.map((workspace) =>
          workspace.workspace_id === activated.workspace_id
            ? activated
            : { ...workspace, is_active: false },
        ),
      )
    } catch (workspaceError) {
      console.error(workspaceError)
    }
  }

  const openSession = async (session: Session, options?: { forceWorkspaceSync?: boolean }) => {
    const shouldSyncWorkspace =
      Boolean(options?.forceWorkspaceSync) || session.workspace_id !== currentWorkspaceId

    if (shouldSyncWorkspace) {
      await syncWorkspaceForSession(session, true)
    }

    setCurrentSession(session.session_id)
    try {
      const {
        messages: msgs,
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
            messages: mapMessages(panel_messages?.[panel.panel_id] ?? msgs),
          })),
        )
        sessionPanels.forEach((panel) => {
          const restoredMessages = panel_messages?.[panel.panel_id] ?? msgs
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
        loadMessagesToAllPanels(msgs)
        const workflowNodes = findLatestWorkflowNodes(msgs)
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
    } catch (e) {
      console.error(e)
    }
  }

  const handleSelectSession = async (session: Session) => {
    if (session.session_id === currentSessionId) return
    setMovingSessionId(null)
    const normalizedSearch = search.trim()
    await openSession(session, {
      forceWorkspaceSync: Boolean(normalizedSearch && session.workspace_id !== currentWorkspaceId),
    })
  }

  const handleOpenBookmark = async (bookmark: (typeof bookmarks)[number]) => {
    if (!bookmark.sessionId) return

    setMovingSessionId(null)
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
      setError('未找到对应的书签会话。')
      return
    }

    await openSession(targetSession, { forceWorkspaceSync: true })
  }

  const handleExport = async (e: React.MouseEvent, session: Session) => {
    e.stopPropagation()
    setExportingId(session.session_id)
    try {
      const { messages } = await getSessionMessages(session.session_id)
      const lines: string[] = [`# ${session.title || '对话记录'}`, '']
      const dateStr = new Date(session.updated_at * 1000).toLocaleString('zh-CN')
      lines.push(`> 导出时间：${dateStr}`, '')
      for (const msg of messages) {
        if (msg.role === 'user') {
          lines.push(`**用户**`, '', msg.content, '')
        } else if (msg.role === 'assistant') {
          const model = msg.model_id ? ` (${msg.model_id})` : ''
          lines.push(`**AI${model}**`, '', msg.content, '')
        }
      }
      const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${(session.title || '对话记录').replace(/[/\\?%*:|"<>]/g, '-')}.md`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('导出失败', e)
    } finally {
      setExportingId(null)
    }
  }

  const handleDelete = async (e: React.MouseEvent, session: Session) => {
    e.stopPropagation()
    setDeletingId(session.session_id)
    setError('')
    try {
      await deleteSession(session.session_id)
      removeSession(session.session_id)
      adjustWorkspaceSessionCount(session.workspace_id, -1)
      bookmarks
        .filter((bookmark) => bookmark.sessionId === session.session_id)
        .forEach((bookmark) => removeBookmark(bookmark.id))
      if (currentSessionId === session.session_id) {
        setCurrentSession(null)
        clearMessages()
        storePanels.forEach((panel) => clearWorkflow(panel.id))
      }
    } finally {
      setDeletingId(null)
    }
  }

  const handleRemoveBookmark = async (bookmarkId: string, source: 'remote' | 'local' = 'remote') => {
    setRemovingBookmarkId(bookmarkId)
    setError('')
    try {
      if (source === 'remote') {
        await deleteBookmarkRequest(bookmarkId)
      }
      removeBookmark(bookmarkId)
    } catch (bookmarkError) {
      console.error(bookmarkError)
      setError((bookmarkError as Error).message ?? '移除书签失败。')
    } finally {
      setRemovingBookmarkId(null)
    }
  }

  const cancelEditing = () => {
    setEditingSessionId(null)
    setEditingTitle('')
    setEditingTags('')
  }

  const parseTagDraft = (value: string): string[] =>
    value
      .split(/[\n,，]/)
      .map((item) => item.trim())
      .filter(Boolean)

  const applySessionPatch = async (
    e: React.MouseEvent | null,
    sessionId: string,
    patch: {
      title?: string
      is_archived?: boolean
      is_favorite?: boolean
      is_pinned?: boolean
      tags?: string[]
    },
  ) => {
    e?.stopPropagation()
    setSavingId(sessionId)
    setError('')
    try {
      const updated = await updateSessionMeta(sessionId, patch)
      updateSession(sessionId, updated)
      if (editingSessionId === sessionId) {
        cancelEditing()
      }
      if (viewMode === 'favorite' && updated.is_archived) {
        setViewMode('all')
      }
    } catch (saveError) {
      console.error(saveError)
      setError((saveError as Error).message ?? '更新对话失败。')
    } finally {
      setSavingId((current) => (current === sessionId ? null : current))
    }
  }

  const startEditing = (e: React.MouseEvent, session: Session) => {
    e.stopPropagation()
    setEditingSessionId(session.session_id)
    setEditingTitle(session.title || '新建对话')
    setEditingTags(session.tags.join(', '))
    setMovingSessionId(null)
    setError('')
  }

  const handleMoveSession = async (
    event: React.ChangeEvent<HTMLSelectElement>,
    session: Session,
  ) => {
    event.stopPropagation()
    const nextWorkspaceId = event.target.value
    if (!nextWorkspaceId || nextWorkspaceId === session.workspace_id) {
      setMovingSessionId(null)
      return
    }

    setSavingId(session.session_id)
    setError('')
    try {
      const updated = await updateSessionMeta(session.session_id, {
        workspace_id: nextWorkspaceId,
      })
      adjustWorkspaceSessionCount(session.workspace_id, -1)
      adjustWorkspaceSessionCount(nextWorkspaceId, 1)
      setMovingSessionId(null)

      if (updated.workspace_id !== currentWorkspaceId) {
        removeSession(session.session_id)
        if (currentSessionId === session.session_id) {
          setCurrentSession(null)
          clearMessages()
          storePanels.forEach((panel) => clearWorkflow(panel.id))
        }
        return
      }

      updateSession(session.session_id, updated)
    } catch (moveError) {
      console.error(moveError)
      setError((moveError as Error).message ?? '移动对话失败。')
    } finally {
      setSavingId((current) => (current === session.session_id ? null : current))
    }
  }

  const saveEditing = async () => {
    if (!editingSessionId) return
    const nextTitle = editingTitle.trim()
    if (!nextTitle) {
      setError('对话标题不能为空。')
      return
    }
    await applySessionPatch(null, editingSessionId, {
      title: nextTitle,
      tags: parseTagDraft(editingTags),
    })
  }

  const handleEditKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      void saveEditing()
      return
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      cancelEditing()
    }
  }

  const formatTime = (ts: number) => {
    const d = new Date(ts * 1000)
    const now = new Date()
    const diff = now.getTime() - d.getTime()
    if (diff < 86400000) {
      return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    }
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  }

  const counts = useMemo(
    () => ({
      all: sessions.filter((session) => !session.is_archived).length,
      favorite: sessions.filter((session) => session.is_favorite && !session.is_archived).length,
      archived: sessions.filter((session) => session.is_archived).length,
    }),
    [sessions],
  )

  const allTags = useMemo(() => {
    const tagSet = new Set<string>()
    sessions.forEach((session) => session.tags.forEach((tag) => tagSet.add(tag)))
    return Array.from(tagSet).slice(0, 12)
  }, [sessions])

  const filteredSessions = useMemo(() => {
    return sessions.filter((session) => {
      if (viewMode === 'all' && session.is_archived) return false
      if (viewMode === 'favorite' && (!session.is_favorite || session.is_archived)) return false
      if (viewMode === 'archived' && !session.is_archived) return false
      if (tagFilter && !session.tags.includes(tagFilter)) return false
      return true
    })
  }, [sessions, viewMode, tagFilter])

  const filteredBookmarks = useMemo(() => {
    const keyword = bookmarkSearch.trim().toLowerCase()
    if (!keyword) return bookmarks

    return bookmarks.filter((bookmark) => {
      return [
        bookmark.sessionTitle,
        bookmark.content,
        bookmark.modelId ?? '',
      ].some((value) => value.toLowerCase().includes(keyword))
    })
  }, [bookmarkSearch, bookmarks])

  const bookmarkGroups = useMemo<BookmarkGroup[]>(() => {
    const groups = new Map<string, BookmarkGroup>()

    filteredBookmarks.forEach((bookmark) => {
      const title = bookmark.sessionTitle.trim() || '未命名会话'
      const key = bookmark.sessionId || `session-title:${title}`
      const existing = groups.get(key)

      if (existing) {
        existing.items.push(bookmark)
        existing.updatedAt = Math.max(
          existing.updatedAt,
          bookmark.updatedAt || bookmark.createdAt || 0,
        )
        return
      }

      groups.set(key, {
        key,
        title,
        updatedAt: bookmark.updatedAt || bookmark.createdAt || 0,
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
  }, [filteredBookmarks])

  const canDragSort =
    !search.trim() &&
    !showBookmarks &&
    viewMode === 'all' &&
    !reorderingSessions

  const emptyStateMessage = (() => {
    if (search.trim()) return '没有找到匹配的跨会话结果。'
    if (viewMode === 'favorite') return '还没有收藏的对话。'
    if (viewMode === 'archived') return '没有已归档的对话。'
    return '暂无对话记录'
  })()

  const handleSessionDrop = async (targetSessionId: string) => {
    if (!canDragSort || !draggingSessionId || draggingSessionId === targetSessionId) return

    const currentOrder = filteredSessions.map((session) => session.session_id)
    const sourceIndex = currentOrder.indexOf(draggingSessionId)
    const targetIndex = currentOrder.indexOf(targetSessionId)
    if (sourceIndex < 0 || targetIndex < 0 || sourceIndex === targetIndex) return

    const nextOrder = [...currentOrder]
    const [movedSessionId] = nextOrder.splice(sourceIndex, 1)
    nextOrder.splice(targetIndex, 0, movedSessionId)

    const orderSize = nextOrder.length
    const orderMap = new Map(
      nextOrder.map((sessionId, index) => [sessionId, orderSize - index]),
    )
    const optimisticSessions = sessions.map((session) => {
      const order = orderMap.get(session.session_id)
      if (order === undefined) return session
      return {
        ...session,
        session_order: order,
      }
    })

    setSessions(optimisticSessions)
    setReorderingSessions(true)
    setError('')
    try {
      const orderedSessions = await reorderSessions(nextOrder, {
        workspace_id: currentWorkspaceId ?? undefined,
      })
      setSessions(orderedSessions)
    } catch (reorderError) {
      console.error(reorderError)
      setError((reorderError as Error).message ?? '会话排序失败。')
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

  const sidebarContent = (
    <>
        <div className="flex items-center justify-between border-b border-bg-border px-4 py-4">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent-blue/20">
            <Brain size={18} className="text-accent-blue" />
          </div>
          <span className="truncate text-sm font-semibold text-text-primary">企业 AI 助手</span>
        </div>
        <button
          onClick={toggleSidebar}
          className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
          title="收起侧边栏"
        >
          <ChevronLeft size={16} />
        </button>
      </div>

      <div className="p-3">
        <div className="mb-3 rounded-2xl border border-bg-border bg-bg-secondary/60 p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-[11px] font-medium text-text-primary">
              <FolderOpen size={13} className="text-accent-blue" />
              工作区
            </div>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={openWorkspaceEditor}
                className="rounded-lg p-1 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                title="编辑工作区"
                disabled={!currentWorkspace}
              >
                <Pencil size={12} />
              </button>
              <button
                type="button"
                onClick={openWorkspaceDeletePrompt}
                className="rounded-lg p-1 text-text-secondary transition-colors hover:bg-accent-red/10 hover:text-accent-red disabled:cursor-not-allowed disabled:opacity-40"
                title={
                  currentWorkspace?.workspace_id === DEFAULT_WORKSPACE_ID
                    ? '默认工作区不可删除'
                    : '删除工作区'
                }
                disabled={!currentWorkspace || currentWorkspace.workspace_id === DEFAULT_WORKSPACE_ID}
              >
                <Trash2 size={12} />
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowWorkspaceForm((current) => !current)
                  setShowWorkspaceEditForm(false)
                  setShowWorkspaceDeleteForm(false)
                  setError('')
                }}
                className="rounded-lg p-1 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                title="新建工作区"
              >
                <Plus size={12} />
              </button>
            </div>
          </div>
          <select
            value={currentWorkspaceId ?? ''}
            onChange={(event) => {
              void handleSelectWorkspace(event.target.value)
            }}
            className="w-full rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-xs text-text-primary outline-none"
          >
            {workspaces.map((workspace) => (
              <option key={workspace.workspace_id} value={workspace.workspace_id}>
                {workspace.name}（{workspace.session_count} 个对话）
              </option>
            ))}
          </select>
          {currentWorkspace && (
            <div className="mt-3 rounded-xl border border-bg-border bg-bg-primary px-3 py-2.5">
              <div className="flex items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${WORKSPACE_COLOR_TONES[currentWorkspace.color]}`}
                  >
                    {WORKSPACE_COLOR_LABELS[currentWorkspace.color]}
                  </span>
                  <div className="truncate text-xs font-medium text-text-primary">
                    {currentWorkspace.name}
                  </div>
                </div>
                <span className="shrink-0 text-[10px] text-text-secondary">
                  {currentWorkspace.session_count} 个对话
                </span>
              </div>
              {currentWorkspace.description && (
                <div className="mt-1.5 text-[11px] leading-relaxed text-text-secondary">
                  {currentWorkspace.description}
                </div>
              )}
              {currentWorkspace.workspace_id === DEFAULT_WORKSPACE_ID && (
                <div className="mt-1.5 text-[10px] text-text-secondary">
                  默认工作区受保护，不能被删除。
                </div>
              )}
            </div>
          )}
          {showWorkspaceForm && (
            <div className="mt-3 space-y-2 rounded-xl border border-bg-border bg-bg-primary p-2.5">
              <input
                value={workspaceName}
                onChange={(event) => setWorkspaceName(event.target.value)}
                placeholder="工作区名称"
                className="w-full rounded-lg border border-bg-border bg-bg-secondary px-2.5 py-2 text-xs text-text-primary outline-none placeholder:text-text-secondary"
              />
              <select
                value={workspaceColor}
                onChange={(event) => setWorkspaceColor(event.target.value as Workspace['color'])}
                className="w-full rounded-lg border border-bg-border bg-bg-secondary px-2.5 py-2 text-xs text-text-primary outline-none"
              >
                <option value="blue">蓝色</option>
                <option value="green">绿色</option>
                <option value="amber">琥珀</option>
                <option value="rose">玫瑰</option>
                <option value="slate">石板</option>
              </select>
              <div className="flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowWorkspaceForm(false)
                    setWorkspaceName('')
                    setWorkspaceColor('blue')
                  }}
                  className="rounded-lg px-2 py-1 text-[11px] text-text-secondary transition-colors hover:text-text-primary"
                >
                  取消
                </button>
                <button
                  type="button"
                  onClick={() => {
                    void handleCreateWorkspace()
                  }}
                  disabled={creatingWorkspace}
                  className="rounded-lg border border-bg-border px-2.5 py-1 text-[11px] text-text-primary transition-colors hover:border-accent-blue/40 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {creatingWorkspace ? '创建中…' : '创建'}
                </button>
              </div>
            </div>
          )}
          {showWorkspaceEditForm && currentWorkspace && (
            <div className="mt-3 space-y-2 rounded-xl border border-bg-border bg-bg-primary p-2.5">
              <input
                value={workspaceEditName}
                onChange={(event) => setWorkspaceEditName(event.target.value)}
                placeholder="工作区名称"
                className="w-full rounded-lg border border-bg-border bg-bg-secondary px-2.5 py-2 text-xs text-text-primary outline-none placeholder:text-text-secondary"
              />
              <textarea
                value={workspaceEditDescription}
                onChange={(event) => setWorkspaceEditDescription(event.target.value)}
                placeholder="工作区描述"
                className="min-h-[72px] w-full resize-none rounded-lg border border-bg-border bg-bg-secondary px-2.5 py-2 text-xs text-text-primary outline-none placeholder:text-text-secondary"
              />
              <select
                value={workspaceEditColor}
                onChange={(event) => setWorkspaceEditColor(event.target.value as Workspace['color'])}
                className="w-full rounded-lg border border-bg-border bg-bg-secondary px-2.5 py-2 text-xs text-text-primary outline-none"
              >
                <option value="blue">蓝色</option>
                <option value="green">绿色</option>
                <option value="amber">琥珀</option>
                <option value="rose">玫瑰</option>
                <option value="slate">石板</option>
              </select>
              <div className="flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={cancelWorkspaceEditor}
                  className="rounded-lg px-2 py-1 text-[11px] text-text-secondary transition-colors hover:text-text-primary"
                >
                  取消
                </button>
                <button
                  type="button"
                  onClick={() => {
                    void handleUpdateWorkspace()
                  }}
                  disabled={updatingWorkspace}
                  className="rounded-lg border border-bg-border px-2.5 py-1 text-[11px] text-text-primary transition-colors hover:border-accent-blue/40 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {updatingWorkspace ? '保存中…' : '保存'}
                </button>
              </div>
            </div>
          )}
          {showWorkspaceDeleteForm &&
            currentWorkspace &&
            currentWorkspace.workspace_id !== DEFAULT_WORKSPACE_ID && (
              <div className="mt-3 space-y-2 rounded-xl border border-accent-red/20 bg-accent-red/5 p-2.5">
                <div className="text-xs font-medium text-text-primary">删除工作区</div>
                <div className="text-[11px] leading-relaxed text-text-secondary">
                  删除前会先把当前工作区内的全部对话迁移到其他工作区。
                </div>
                <select
                  value={workspaceDeleteTargetId}
                  onChange={(event) => setWorkspaceDeleteTargetId(event.target.value)}
                  className="w-full rounded-lg border border-bg-border bg-bg-secondary px-2.5 py-2 text-xs text-text-primary outline-none"
                >
                  {workspaceDeleteTargets.map((workspace) => (
                    <option key={workspace.workspace_id} value={workspace.workspace_id}>
                      迁移到 {workspace.name}
                    </option>
                  ))}
                </select>
                <div className="flex items-center justify-end gap-2">
                  <button
                    type="button"
                    onClick={cancelWorkspaceDelete}
                    className="rounded-lg px-2 py-1 text-[11px] text-text-secondary transition-colors hover:text-text-primary"
                  >
                    取消
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      void handleDeleteWorkspace()
                    }}
                    disabled={deletingWorkspace || workspaceDeleteTargets.length === 0}
                    className="rounded-lg border border-accent-red/30 px-2.5 py-1 text-[11px] text-accent-red transition-colors hover:bg-accent-red/10 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {deletingWorkspace ? '删除中…' : '确认删除'}
                  </button>
                </div>
              </div>
            )}
        </div>
        <Button
          variant="outline"
          className="w-full justify-center gap-2 border-dashed border-bg-border hover:border-accent-blue/50 hover:bg-accent-blue/5"
          onClick={handleNewChat}
          loading={loadingNew}
        >
          <Plus size={15} />
          新建对话
        </Button>
      </div>

      <div className="px-3 pb-3">
        <label className="flex items-center gap-2 rounded-xl border border-bg-border bg-bg-secondary px-3 py-2">
          <Search size={13} className="text-text-secondary" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="搜索标题、标签或消息内容"
            className="w-full bg-transparent text-xs text-text-primary outline-none placeholder:text-text-secondary"
          />
        </label>

        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() =>
              setShowBookmarks((current) => {
                if (current) {
                  setBookmarkSearch('')
                }
                return !current
              })
            }
            className={`rounded-full px-2.5 py-1 text-[11px] transition-colors flex items-center gap-1 ${
              showBookmarks
                ? 'bg-amber-400/15 text-amber-400'
                : 'bg-bg-secondary text-text-secondary hover:text-text-primary'
            }`}
          >
            <Bookmark size={10} />
            书签 {bookmarks.length > 0 ? bookmarks.length : ''}
          </button>
          {([
            ['all', `全部 ${counts.all}`],
            ['favorite', `收藏 ${counts.favorite}`],
            ['archived', `归档 ${counts.archived}`],
          ] as Array<[SessionViewMode, string]>).map(([value, label]) => {
            const active = viewMode === value
            return (
              <button
                key={value}
                type="button"
                onClick={() => setViewMode(value)}
                className={`rounded-full px-2.5 py-1 text-[11px] transition-colors ${
                  active
                    ? 'bg-accent-blue/15 text-accent-blue'
                    : 'bg-bg-secondary text-text-secondary hover:text-text-primary'
                }`}
              >
                {label}
              </button>
            )
          })}
        </div>
        {showBookmarks && (
          <label className="mt-3 flex items-center gap-2 rounded-xl border border-bg-border bg-bg-secondary px-3 py-2">
            <Search size={13} className="text-text-secondary" />
            <input
              value={bookmarkSearch}
              onChange={(event) => setBookmarkSearch(event.target.value)}
              placeholder="搜索书签内容、会话名或模型"
              className="w-full bg-transparent text-xs text-text-primary outline-none placeholder:text-text-secondary"
            />
          </label>
        )}
        {!showBookmarks && allTags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {allTags.map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={() => setTagFilter(tagFilter === tag ? null : tag)}
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] transition-colors ${
                  tagFilter === tag
                    ? 'bg-accent-blue/20 text-accent-blue ring-1 ring-accent-blue/30'
                    : 'bg-bg-secondary text-text-secondary hover:text-text-primary'
                }`}
              >
                <Tag size={8} />
                {tag}
              </button>
            ))}
          </div>
        )}
        {canDragSort && filteredSessions.length > 1 && (
          <p className="mt-2 text-[10px] text-text-secondary/65">
            提示：可拖拽会话调整顺序
          </p>
        )}

        {error && (
          <div className="mt-3 rounded-xl border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red">
            {error}
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {/* 书签视图 */}
        {showBookmarks && (
          <div className="mb-2">
            {bookmarks.length === 0 ? (
              <div className="py-6 text-center text-xs text-text-secondary">暂无书签消息</div>
            ) : bookmarkGroups.length === 0 ? (
              <div className="py-6 text-center text-xs text-text-secondary">
                没有找到匹配的书签。
              </div>
            ) : (
              <div className="space-y-3">
                {bookmarkGroups.map((group) => (
                  <section
                    key={group.key}
                    className="rounded-2xl border border-bg-border bg-bg-secondary/35 p-2"
                  >
                    <div className="mb-2 flex items-center justify-between gap-2 px-1">
                      <div className="min-w-0">
                        <div className="truncate text-xs font-medium text-text-primary">
                          {group.title}
                        </div>
                        <div className="mt-0.5 text-[10px] text-text-secondary/60">
                          {group.items.length} 条书签
                        </div>
                      </div>
                      <div className="shrink-0 text-[10px] text-text-secondary/55">
                        {formatTime(group.updatedAt)}
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      {group.items.map((bm) => (
                        <div
                          key={bm.id}
                          role="button"
                          tabIndex={0}
                          onClick={() => {
                            void handleOpenBookmark(bm)
                          }}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter' || event.key === ' ') {
                              event.preventDefault()
                              void handleOpenBookmark(bm)
                            }
                          }}
                          className="rounded-xl border border-bg-border bg-bg-tertiary/40 px-3 py-2.5 text-xs transition-colors hover:border-accent-blue/35 hover:bg-accent-blue/5"
                        >
                          <div className="mb-1.5 flex items-start justify-between gap-2">
                            <div className="min-w-0 flex-1">
                              <div className="truncate text-[10px] text-text-secondary/60">
                                {bm.modelId ? `${bm.modelId} · ` : ''}
                                {formatTime(bm.updatedAt || bm.createdAt)}
                              </div>
                            </div>
                            <div className="flex shrink-0 items-center gap-1">
                              <button
                                type="button"
                                onClick={(event) => {
                                  event.stopPropagation()
                                  pushComposerSeed({ text: bm.content })
                                }}
                                className="rounded p-0.5 text-text-secondary/50 transition-colors hover:text-accent-blue"
                                title="填入输入框"
                              >
                                <Plus size={10} />
                              </button>
                              <button
                                type="button"
                                onClick={(event) => {
                                  event.stopPropagation()
                                  void handleRemoveBookmark(bm.id, bm.source ?? 'remote')
                                }}
                                disabled={removingBookmarkId === bm.id}
                                className="rounded p-0.5 text-text-secondary/50 transition-colors hover:text-accent-red"
                                title="移除书签"
                              >
                                <X size={10} />
                              </button>
                            </div>
                          </div>
                          <p className="line-clamp-3 leading-relaxed text-text-secondary">
                            {bm.content}
                          </p>
                          <div className="mt-2 text-[10px] text-text-secondary/55">
                            点击可跳转到原消息
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            )}
          </div>
        )}

        {!showBookmarks && filteredSessions.length === 0 ? (
          <div className="py-8 text-center text-xs text-text-secondary">{emptyStateMessage}</div>
        ) : !showBookmarks && (
          <div className="space-y-1">
            {filteredSessions.map((session) => {
              const isActive = session.session_id === currentSessionId
              const isEditing = editingSessionId === session.session_id
              const showActions =
                isMobile ||
                isEditing ||
                movingSessionId === session.session_id ||
                hoveredId === session.session_id ||
                deletingId === session.session_id ||
                savingId === session.session_id ||
                isActive

              return (
                <div
                  key={session.session_id}
                  className={`group cursor-pointer rounded-xl px-3 py-2.5 transition-colors ${
                    isActive
                      ? 'bg-accent-blue/15 text-text-primary'
                      : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                  } ${
                    draggingSessionId === session.session_id
                      ? 'opacity-60'
                      : ''
                  } ${
                    dragOverSessionId === session.session_id &&
                    draggingSessionId !== session.session_id &&
                    canDragSort
                      ? 'ring-1 ring-accent-blue/50'
                      : ''
                  }`}
                  draggable={canDragSort && !isEditing}
                  onClick={() => {
                    if (!isEditing && !draggingSessionId) {
                      void handleSelectSession(session)
                    }
                  }}
                  onDragStart={(event) => {
                    if (!canDragSort || isEditing) return
                    setDraggingSessionId(session.session_id)
                    event.dataTransfer.effectAllowed = 'move'
                    event.dataTransfer.setData('text/plain', session.session_id)
                  }}
                  onDragOver={(event) => {
                    if (!canDragSort || isEditing) return
                    event.preventDefault()
                    if (dragOverSessionId !== session.session_id) {
                      setDragOverSessionId(session.session_id)
                    }
                  }}
                  onDragLeave={() => {
                    if (dragOverSessionId === session.session_id) {
                      setDragOverSessionId(null)
                    }
                  }}
                  onDrop={(event) => {
                    if (!canDragSort || isEditing) return
                    event.preventDefault()
                    void handleSessionDrop(session.session_id)
                  }}
                  onDragEnd={() => {
                    setDraggingSessionId(null)
                    setDragOverSessionId(null)
                  }}
                  onMouseEnter={() => setHoveredId(session.session_id)}
                  onMouseLeave={() => setHoveredId(null)}
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
                            onChange={(event) => setEditingTitle(event.target.value)}
                            onKeyDown={handleEditKeyDown}
                            className="w-full rounded-lg border border-bg-border bg-bg-primary px-2.5 py-1.5 text-xs text-text-primary outline-none"
                            placeholder="对话标题"
                            autoFocus
                          />
                          <div className="flex items-start gap-2 rounded-lg border border-bg-border bg-bg-primary px-2.5 py-1.5">
                            <Tag size={12} className="mt-0.5 shrink-0 text-text-secondary" />
                            <input
                              value={editingTags}
                              onChange={(event) => setEditingTags(event.target.value)}
                              onKeyDown={handleEditKeyDown}
                              className="w-full bg-transparent text-[11px] text-text-primary outline-none placeholder:text-text-secondary"
                              placeholder="标签，用逗号分隔"
                            />
                          </div>
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation()
                                cancelEditing()
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
                                void saveEditing()
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
                          void applySessionPatch(event, session.session_id, {
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
                          void applySessionPatch(event, session.session_id, {
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
                          setMovingSessionId((current) =>
                            current === session.session_id ? null : session.session_id,
                          )
                          setEditingSessionId(null)
                          setError('')
                        }}
                        className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                        disabled={savingId === session.session_id}
                        title="移动到工作区"
                      >
                        <FolderOpen size={12} />
                      </button>
                      <button
                        type="button"
                        onClick={(event) => startEditing(event, session)}
                        className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                        disabled={savingId === session.session_id}
                        title="重命名与编辑标签"
                      >
                        <Pencil size={12} />
                      </button>
                      <button
                        type="button"
                        onClick={(event) => {
                          void applySessionPatch(event, session.session_id, {
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
                        onClick={(event) => void handleExport(event, session)}
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
                        onClick={(event) => handleDelete(event, session)}
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
                          void handleMoveSession(event, session)
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
            })}
          </div>
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
      <div className="flex w-14 shrink-0 flex-col items-center gap-4 border-r border-bg-border bg-bg-primary py-4">
        <button
          onClick={toggleSidebar}
          className="rounded-lg p-2 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
          title="展开侧边栏"
        >
          <Brain size={20} />
        </button>
        <button
          onClick={handleNewChat}
          className="rounded-lg p-2 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
          title="新建对话"
        >
          <Plus size={20} />
        </button>
      </div>
    )
  }

  if (isMobile) {
    return (
      <>
        <button
          type="button"
          aria-label="关闭侧边栏遮罩"
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
