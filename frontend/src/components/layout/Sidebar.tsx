import React, { useEffect, useState } from 'react'
import { Plus, MessageSquare, Trash2, Settings, ChevronLeft, Brain } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import { getSessions, createSession, deleteSession, getSessionMessages } from '../../api/client'
import type { Session } from '../../api/client'
import { Button } from '../ui/Button'

export const Sidebar: React.FC = () => {
  const {
    sessions,
    currentSessionId,
    sidebarOpen,
    setSessions,
    setCurrentSession,
    addSession,
    removeSession,
    updateSession,
    clearMessages,
    loadMessagesToAllPanels,
    setSettingsOpen,
    toggleSidebar,
    setSidebarOpen,
  } = useChatStore()

  const [loadingNew, setLoadingNew] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768)

  useEffect(() => {
    getSessions().then(setSessions).catch(console.error)
  }, [setSessions])

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
    try {
      const s = await createSession('New Chat')
      addSession({
        session_id: s.session_id,
        title: s.title,
        created_at: Date.now() / 1000,
        updated_at: Date.now() / 1000,
        message_count: 0,
      })
      setCurrentSession(s.session_id)
      clearMessages()
      if (isMobile) {
        setSidebarOpen(false)
      }
    } finally {
      setLoadingNew(false)
    }
  }

  const handleSelectSession = async (session: Session) => {
    if (session.session_id === currentSessionId) return
    setCurrentSession(session.session_id)
    try {
      const { messages: msgs, total_messages } = await getSessionMessages(session.session_id)
      loadMessagesToAllPanels(msgs)
      updateSession(session.session_id, { message_count: total_messages })
      if (isMobile) {
        setSidebarOpen(false)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation()
    setDeletingId(sessionId)
    try {
      await deleteSession(sessionId)
      removeSession(sessionId)
      if (currentSessionId === sessionId) {
        setCurrentSession(null)
        clearMessages()
      }
    } finally {
      setDeletingId(null)
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

  const sidebarContent = (
    <>
      <div className="flex items-center justify-between border-b border-bg-border px-4 py-4">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent-blue/20">
            <Brain size={18} className="text-accent-blue" />
          </div>
          <span className="truncate text-sm font-semibold text-text-primary">Enterprise AI</span>
        </div>
        <button
          onClick={toggleSidebar}
          className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
          title="Close sidebar"
        >
          <ChevronLeft size={16} />
        </button>
      </div>

      <div className="p-3">
        <Button
          variant="outline"
          className="w-full justify-center gap-2 border-dashed border-bg-border hover:border-accent-blue/50 hover:bg-accent-blue/5"
          onClick={handleNewChat}
          loading={loadingNew}
        >
          <Plus size={15} />
          New Chat
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {sessions.length === 0 ? (
          <div className="py-8 text-center text-xs text-text-secondary">No chat history</div>
        ) : (
          <div className="space-y-0.5">
            {sessions.map((session) => {
              const isActive = session.session_id === currentSessionId
              return (
                <div
                  key={session.session_id}
                  className={`group flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2.5 transition-colors ${
                    isActive
                      ? 'bg-accent-blue/15 text-text-primary'
                      : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                  }`}
                  onClick={() => handleSelectSession(session)}
                  onMouseEnter={() => setHoveredId(session.session_id)}
                  onMouseLeave={() => setHoveredId(null)}
                >
                  <MessageSquare
                    size={14}
                    className={`shrink-0 ${isActive ? 'text-accent-blue' : ''}`}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-xs font-medium">{session.title || 'New Chat'}</div>
                    <div className="mt-0.5 text-[10px] text-text-secondary/70">
                      {formatTime(session.updated_at)} · {session.message_count} msgs
                    </div>
                  </div>
                  {(hoveredId === session.session_id || deletingId === session.session_id) && (
                    <button
                      onClick={(e) => handleDelete(e, session.session_id)}
                      className="shrink-0 rounded p-0.5 text-text-secondary transition-colors hover:text-accent-red"
                      disabled={deletingId === session.session_id}
                      title="Delete chat"
                    >
                      {deletingId === session.session_id ? (
                        <span className="block h-3 w-3 rounded-full border border-current border-t-transparent animate-spin" />
                      ) : (
                        <Trash2 size={12} />
                      )}
                    </button>
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
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
        >
          <Settings size={15} />
          Settings & Upload
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
          title="Open sidebar"
        >
          <Brain size={20} />
        </button>
        <button
          onClick={handleNewChat}
          className="rounded-lg p-2 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
          title="New chat"
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
          aria-label="close-sidebar-overlay"
          onClick={toggleSidebar}
          className="fixed inset-0 z-30 bg-black/50 backdrop-blur-[1px]"
        />
        <aside className="fixed inset-y-0 left-0 z-40 flex w-[min(18rem,calc(100vw-1rem))] max-w-full flex-col border-r border-bg-border bg-bg-primary shadow-2xl animate-slide-in">
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
