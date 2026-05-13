import type { ChangeEvent, MouseEvent } from 'react'
import { useState } from 'react'
import {
  deleteSession,
  getSessionMessages,
  updateSessionMeta,
} from '../../../api/client'
import type { Session } from '../../../api/client'
import { useChatStore } from '../../../stores/chatStore'
import type { SessionViewMode } from './sidebarConstants'

interface UseSidebarSessionMutationsOptions {
  currentSessionId: string | null
  currentWorkspaceId: string | null
  editingSessionId: string | null
  viewMode: SessionViewMode
  cancelEditing: () => void
  removeBookmarksForSession: (sessionId: string) => void
  resetPanelWorkflows: () => void
  setMovingSessionId: (sessionId: string | null) => void
  setViewMode: (mode: SessionViewMode) => void
  setError: (message: string) => void
}

export function useSidebarSessionMutations({
  currentSessionId,
  currentWorkspaceId,
  editingSessionId,
  viewMode,
  cancelEditing,
  removeBookmarksForSession,
  resetPanelWorkflows,
  setMovingSessionId,
  setViewMode,
  setError,
}: UseSidebarSessionMutationsOptions) {
  const {
    setCurrentSession,
    removeSession,
    updateSession,
    adjustWorkspaceSessionCount,
    clearMessages,
  } = useChatStore()

  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [exportingId, setExportingId] = useState<string | null>(null)

  const handleExport = async (event: MouseEvent, session: Session) => {
    event.stopPropagation()
    setExportingId(session.session_id)
    try {
      const { messages } = await getSessionMessages(session.session_id)
      const lines: string[] = [`# ${session.title || '对话记录'}`, '']
      const dateStr = new Date(session.updated_at * 1000).toLocaleString('zh-CN')
      lines.push(`> 导出时间：${dateStr}`, '')
      for (const message of messages) {
        if (message.role === 'user') {
          lines.push('**用户**', '', message.content, '')
        } else if (message.role === 'assistant') {
          const model = message.model_id ? ` (${message.model_id})` : ''
          lines.push(`**AI${model}**`, '', message.content, '')
        }
      }
      const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${(session.title || '对话记录').replace(/[/\\?%*:|"<>]/g, '-')}.md`
      link.click()
      URL.revokeObjectURL(url)
    } catch (exportError) {
      console.error('导出失败', exportError)
    } finally {
      setExportingId(null)
    }
  }

  const handleDelete = async (event: MouseEvent, session: Session) => {
    event.stopPropagation()
    setDeletingId(session.session_id)
    setError('')
    try {
      await deleteSession(session.session_id)
      removeSession(session.session_id)
      adjustWorkspaceSessionCount(session.workspace_id, -1)
      removeBookmarksForSession(session.session_id)
      if (currentSessionId === session.session_id) {
        setCurrentSession(null)
        clearMessages()
        resetPanelWorkflows()
      }
    } finally {
      setDeletingId(null)
    }
  }

  const applySessionPatch = async (
    event: MouseEvent | null,
    sessionId: string,
    patch: {
      title?: string
      is_archived?: boolean
      is_favorite?: boolean
      is_pinned?: boolean
      tags?: string[]
    },
  ) => {
    event?.stopPropagation()
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
      setError((saveError as Error).message ?? 'Failed to update session.')
    } finally {
      setSavingId((current) => (current === sessionId ? null : current))
    }
  }

  const handleMoveSession = async (
    event: ChangeEvent<HTMLSelectElement>,
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
          resetPanelWorkflows()
        }
        return
      }

      updateSession(session.session_id, updated)
    } catch (moveError) {
      console.error(moveError)
      setError((moveError as Error).message ?? 'Failed to move session.')
    } finally {
      setSavingId((current) => (current === session.session_id ? null : current))
    }
  }

  return {
    deletingId,
    savingId,
    exportingId,
    handleExport,
    handleDelete,
    handleMoveSession,
    applySessionPatch,
  }
}
