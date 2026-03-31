import React, { useEffect, useState } from 'react'
import { PanelLeftOpen, Plus, Minus, Globe, Settings, SquarePen, UserCog } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import { Button } from '../ui/Button'
import { createSession, getSystemPrompts } from '../../api/client'
import type { SystemPrompt } from '../../api/client'

interface HeaderProps {
  onOpenSettings: () => void
}

export const Header: React.FC<HeaderProps> = ({ onOpenSettings }) => {
  const {
    sidebarOpen,
    toggleSidebar,
    panels,
    addPanel,
    removePanel,
    webSearchEnabled,
    setWebSearchEnabled,
    addSession,
    setCurrentSession,
    clearMessages,
    activePromptId,
  } = useChatStore()

  const [activePrompt, setActivePrompt] = useState<SystemPrompt | null>(null)

  useEffect(() => {
    getSystemPrompts()
      .then((list) => {
        const active = list.find((p) => p.is_active) ?? list[0] ?? null
        setActivePrompt(active)
      })
      .catch(() => {})
  }, [activePromptId])

  const handleNewChat = async () => {
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
    } catch {
      // sidebar will show error
    }
  }

  return (
    <header className="flex items-center justify-between h-12 px-4 border-b border-bg-border bg-bg-primary shrink-0">
      {/* Left: sidebar toggle + active role badge */}
      <div className="flex items-center gap-2">
        {!sidebarOpen && (
          <button
            onClick={toggleSidebar}
            className="text-text-secondary hover:text-text-primary hover:bg-bg-hover p-1.5 rounded-lg transition-colors"
            title="展开侧边栏"
          >
            <PanelLeftOpen size={16} />
          </button>
        )}
        <span className="text-text-secondary text-xs">
          {panels.length} 个模型面板
        </span>
        {activePrompt && (
          <button
            onClick={onOpenSettings}
            className="hidden sm:flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] text-text-secondary/70 hover:text-text-primary hover:bg-bg-hover transition-colors border border-bg-border"
            title="当前角色 – 点击进入设置"
          >
            <UserCog size={11} />
            {activePrompt.name}
          </button>
        )}
      </div>

      {/* Center: panel controls */}
      <div className="flex items-center gap-1.5">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => panels.length > 1 && removePanel(panels[panels.length - 1].id)}
          disabled={panels.length <= 1}
          title="减少面板"
        >
          <Minus size={13} />
        </Button>
        <span className="text-text-secondary text-xs w-4 text-center">{panels.length}</span>
        <Button
          variant="ghost"
          size="sm"
          onClick={addPanel}
          disabled={panels.length >= 6}
          title="增加面板"
        >
          <Plus size={13} />
        </Button>
      </div>

      {/* Right: actions */}
      <div className="flex items-center gap-1.5">
        <button
          onClick={() => setWebSearchEnabled(!webSearchEnabled)}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs transition-colors ${
            webSearchEnabled
              ? 'bg-accent-blue/20 text-accent-blue'
              : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
          }`}
          title="联网搜索"
        >
          <Globe size={13} />
          <span className="hidden sm:inline">联网</span>
        </button>
        <button
          onClick={handleNewChat}
          className="text-text-secondary hover:text-text-primary hover:bg-bg-hover p-1.5 rounded-lg transition-colors"
          title="新建对话"
        >
          <SquarePen size={15} />
        </button>
        <button
          onClick={onOpenSettings}
          className="text-text-secondary hover:text-text-primary hover:bg-bg-hover p-1.5 rounded-lg transition-colors"
          title="设置"
        >
          <Settings size={15} />
        </button>
      </div>
    </header>
  )
}
