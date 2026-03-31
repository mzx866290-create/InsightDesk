import React, { useEffect, useState } from 'react'
import { Plus, MessageSquare, Trash2, Settings, ChevronLeft, Brain } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import { getSessions, createSession, deleteSession, getSessionMessages } from '../../api/client'
import type { Session } from '../../api/client'
import { Button } from '../ui/Button'

interface SidebarProps {
  onOpenSettings: () => void
}

export const Sidebar: React.FC<SidebarProps> = ({ onOpenSettings }) => {
  const {
    sessions,
    currentSessionId,
    sidebarOpen,
    setSessions,
    setCurrentSession,
    addSession,
    removeSession,
    clearMessages,
    loadMessages,
    panels,
    toggleSidebar,
  } = useChatStore()

  const [loadingNew, setLoadingNew] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  useEffect(() => {
    getSessions().then(setSessions).catch(console.error)
  }, [setSessions])

  const handleNewChat = async () => {
    setLoadingNew(true)
    try {
      const s = await createSession('新对话')
      addSession({
        session_id: s.session_id,
        title: s.title,
        created_at: Date.now() / 1000,
        updated_at: Date.now() / 1000,
        message_count: 0,
      })
      setCurrentSession(s.session_id)
      clearMessages()
    } finally {
      setLoadingNew(false)
    }
  }

  const handleSelectSession = async (session: Session) => {
    if (session.session_id === currentSessionId) return
    setCurrentSession(session.session_id)
    try {
      const { messages: msgs } = await getSessionMessages(session.session_id)
      if (panels.length > 0) {
        loadMessages(panels[0].id, msgs)
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

  if (!sidebarOpen) {
    return (
      <div className="flex flex-col items-center w-14 border-r border-bg-border bg-bg-primary py-4 gap-4 shrink-0">
        <button
          onClick={toggleSidebar}
          className="text-text-secondary hover:text-text-primary hover:bg-bg-hover p-2 rounded-lg transition-colors"
          title="展开侧边栏"
        >
          <Brain size={20} />
        </button>
        <button
          onClick={handleNewChat}
          className="text-text-secondary hover:text-text-primary hover:bg-bg-hover p-2 rounded-lg transition-colors"
          title="新建对话"
        >
          <Plus size={20} />
        </button>
      </div>
    )
  }

  return (
    <aside className="flex flex-col w-64 shrink-0 border-r border-bg-border bg-bg-primary animate-slide-in">
      {/* Logo / Header */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-bg-border">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-accent-blue/20 flex items-center justify-center">
            <Brain size={18} className="text-accent-blue" />
          </div>
          <span className="font-semibold text-text-primary text-sm">企业 AI 知识库</span>
        </div>
        <button
          onClick={toggleSidebar}
          className="text-text-secondary hover:text-text-primary hover:bg-bg-hover p-1.5 rounded-lg transition-colors"
        >
          <ChevronLeft size={16} />
        </button>
      </div>

      {/* New Chat Button */}
      <div className="p-3">
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

      {/* Session List */}
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {sessions.length === 0 ? (
          <div className="text-center text-text-secondary text-xs py-8">
            暂无历史对话
          </div>
        ) : (
          <div className="space-y-0.5">
            {sessions.map((session) => {
              const isActive = session.session_id === currentSessionId
              return (
                <div
                  key={session.session_id}
                  className={`group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
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
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium truncate">
                      {session.title || '新对话'}
                    </div>
                    <div className="text-[10px] text-text-secondary/70 mt-0.5">
                      {formatTime(session.updated_at)} · {session.message_count} 条
                    </div>
                  </div>
                  {(hoveredId === session.session_id || deletingId === session.session_id) && (
                    <button
                      onClick={(e) => handleDelete(e, session.session_id)}
                      className="shrink-0 text-text-secondary hover:text-accent-red p-0.5 rounded transition-colors"
                      disabled={deletingId === session.session_id}
                    >
                      {deletingId === session.session_id ? (
                        <span className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin block" />
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

      {/* Footer */}
      <div className="border-t border-bg-border p-3">
        <button
          onClick={onOpenSettings}
          className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors text-sm"
        >
          <Settings size={15} />
          设置 & 文档上传
        </button>
      </div>
    </aside>
  )
}
