import { useCallback, useEffect, useRef, useState } from 'react'

import { createSession, createSessionShareLink, resetSession } from '../../../api/client'
import type { Session } from '../../../api/client'
import type { HeaderActionFeedbackSetter } from './headerTypes'

interface UseHeaderSessionActionsOptions {
  currentSessionId: string | null
  currentWorkspaceId: string | null
  addSession: (session: Session) => void
  adjustWorkspaceSessionCount: (workspaceId: string, delta: number) => void
  setCurrentSession: (sessionId: string | null) => void
  clearMessages: () => void
  updateSession: (sessionId: string, patch: Partial<Session>) => void
  setActionFeedback: HeaderActionFeedbackSetter
}

export function useHeaderSessionActions({
  currentSessionId,
  currentWorkspaceId,
  addSession,
  adjustWorkspaceSessionCount,
  setCurrentSession,
  clearMessages,
  updateSession,
  setActionFeedback,
}: UseHeaderSessionActionsOptions) {
  const [resetting, setResetting] = useState(false)
  const [resetConfirm, setResetConfirm] = useState(false)
  const [sharingSession, setSharingSession] = useState(false)
  const [sessionShareCopied, setSessionShareCopied] = useState(false)
  const resetConfirmTimerRef = useRef<number | null>(null)
  const shareCopiedTimerRef = useRef<number | null>(null)

  const clearResetConfirmTimer = useCallback(() => {
    if (resetConfirmTimerRef.current !== null) {
      window.clearTimeout(resetConfirmTimerRef.current)
      resetConfirmTimerRef.current = null
    }
  }, [])

  const clearShareCopiedTimer = useCallback(() => {
    if (shareCopiedTimerRef.current !== null) {
      window.clearTimeout(shareCopiedTimerRef.current)
      shareCopiedTimerRef.current = null
    }
  }, [])

  useEffect(() => {
    return () => {
      clearResetConfirmTimer()
      clearShareCopiedTimer()
    }
  }, [clearResetConfirmTimer, clearShareCopiedTimer])

  const handleNewChat = useCallback(async () => {
    try {
      const session = await createSession('新建对话', {
        workspace_id: currentWorkspaceId ?? undefined,
      })
      const workspaceId = session.workspace_id ?? currentWorkspaceId ?? 'workspace-default'
      addSession({
        session_id: session.session_id,
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
      setCurrentSession(session.session_id)
      clearMessages()
    } catch {
      // Sidebar/session loaders surface the detailed creation error.
    }
  }, [
    addSession,
    adjustWorkspaceSessionCount,
    clearMessages,
    currentWorkspaceId,
    setCurrentSession,
  ])

  const handleResetSession = useCallback(async () => {
    if (!resetConfirm) {
      clearResetConfirmTimer()
      setResetConfirm(true)
      resetConfirmTimerRef.current = window.setTimeout(() => {
        setResetConfirm(false)
        resetConfirmTimerRef.current = null
      }, 3000)
      return
    }

    if (!currentSessionId) return
    clearResetConfirmTimer()
    setResetting(true)
    setResetConfirm(false)
    try {
      await resetSession(currentSessionId)
      updateSession(currentSessionId, {
        message_count: 0,
        updated_at: Date.now() / 1000,
      })
      clearMessages()
      setActionFeedback({
        tone: 'success',
        message: '会话已重置。',
      })
    } catch (error) {
      setActionFeedback({
        tone: 'error',
        message: `重置会话失败：${(error as Error).message}`,
      })
    } finally {
      setResetting(false)
    }
  }, [
    clearMessages,
    clearResetConfirmTimer,
    currentSessionId,
    resetConfirm,
    setActionFeedback,
    updateSession,
  ])

  const handleShareSession = useCallback(async () => {
    if (!currentSessionId || sharingSession) return
    setSharingSession(true)
    try {
      const payload = await createSessionShareLink(currentSessionId)
      await navigator.clipboard.writeText(payload.share_url)
      clearShareCopiedTimer()
      setSessionShareCopied(true)
      setActionFeedback({
        tone: 'success',
        message: '分享链接已复制到剪贴板。',
      })
      shareCopiedTimerRef.current = window.setTimeout(() => {
        setSessionShareCopied(false)
        shareCopiedTimerRef.current = null
      }, 2000)
    } catch (error) {
      setActionFeedback({
        tone: 'error',
        message: `创建分享链接失败：${(error as Error).message}`,
      })
    } finally {
      setSharingSession(false)
    }
  }, [
    clearShareCopiedTimer,
    currentSessionId,
    setActionFeedback,
    sharingSession,
  ])

  return {
    resetting,
    resetConfirm,
    sharingSession,
    sessionShareCopied,
    handleNewChat,
    handleResetSession,
    handleShareSession,
  }
}
