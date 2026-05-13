import type { KeyboardEvent, MouseEvent } from 'react'
import { useState } from 'react'
import type { Session } from '../../../api/client'
import { parseSessionTagDraft } from './sidebarModel'

type SessionPatch = {
  title?: string
  is_archived?: boolean
  is_favorite?: boolean
  is_pinned?: boolean
  tags?: string[]
}

type ApplySessionPatch = (
  event: MouseEvent | null,
  sessionId: string,
  patch: SessionPatch,
) => Promise<void>

interface UseSidebarSessionEditingOptions {
  setMovingSessionId: (sessionId: string | null) => void
  setError: (message: string) => void
}

export function useSidebarSessionEditing({
  setMovingSessionId,
  setError,
}: UseSidebarSessionEditingOptions) {
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState('')
  const [editingTags, setEditingTags] = useState('')

  const cancelEditing = () => {
    setEditingSessionId(null)
    setEditingTitle('')
    setEditingTags('')
  }

  const startEditing = (event: MouseEvent, session: Session) => {
    event.stopPropagation()
    setEditingSessionId(session.session_id)
    setEditingTitle(session.title || '新建对话')
    setEditingTags(session.tags.join(', '))
    setMovingSessionId(null)
    setError('')
  }

  const saveEditing = async (applySessionPatch: ApplySessionPatch) => {
    if (!editingSessionId) return
    const nextTitle = editingTitle.trim()
    if (!nextTitle) {
      setError('Session title is required.')
      return
    }
    await applySessionPatch(null, editingSessionId, {
      title: nextTitle,
      tags: parseSessionTagDraft(editingTags),
    })
  }

  const handleEditKeyDown = (
    event: KeyboardEvent<HTMLInputElement>,
    saveCurrentEditing: () => void,
  ) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      saveCurrentEditing()
      return
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      cancelEditing()
    }
  }

  return {
    editingSessionId,
    editingTitle,
    editingTags,
    setEditingTitle,
    setEditingTags,
    startEditing,
    cancelEditing,
    saveEditing,
    handleEditKeyDown,
  }
}
