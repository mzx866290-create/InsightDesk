import React, { useEffect, useRef, useState } from 'react'
import { useChatStore } from '../../stores/chatStore'
import { MessageBubble } from './MessageBubble'
import { ModelSelector } from './ModelSelector'
import type { Panel } from '../../stores/chatStore'
import { Bot, Sparkles, Eraser } from 'lucide-react'
import { clearSessionMessages } from '../../api/client'

interface ChatPanelProps {
  panel: Panel
  isStreaming: boolean
  contextLimit?: number
}

export const ChatPanel: React.FC<ChatPanelProps> = ({ panel, isStreaming, contextLimit = 16 }) => {
  const { removePanel, panels, clearMessages, currentSessionId } = useChatStore()
  const bottomRef = useRef<HTMLDivElement>(null)
  const canRemove = panels.length > 1
  const [confirmClear, setConfirmClear] = useState(false)
  const [clearing, setClearing] = useState(false)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [panel.messages])

  const handleClearContext = async () => {
    if (!confirmClear) {
      setConfirmClear(true)
      setTimeout(() => setConfirmClear(false), 3000)
      return
    }
    setConfirmClear(false)
    setClearing(true)
    try {
      if (currentSessionId) {
        await clearSessionMessages(currentSessionId)
      }
      clearMessages()
    } finally {
      setClearing(false)
    }
  }

  const msgCount = panel.messages.filter((m) => m.role !== 'error').length
  const contextUsed = Math.min(msgCount, contextLimit)

  return (
    <div className="panel-card flex-1 min-w-0">
      {/* Panel Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-bg-border bg-bg-tertiary/50 shrink-0">
        <ModelSelector
          panelId={panel.id}
          modelConfig={panel.modelConfig}
          onRemove={() => removePanel(panel.id)}
          canRemove={canRemove}
        />
        <div className="flex items-center gap-2">
          {isStreaming && (
            <div className="flex items-center gap-1.5 text-accent-blue text-[10px]">
              <Sparkles size={10} className="animate-pulse" />
              生成中…
            </div>
          )}
          {msgCount > 0 && !isStreaming && (
            <span className="text-[10px] text-text-secondary/60" title="当前上下文条数 / 窗口上限">
              {contextUsed}/{contextLimit}
            </span>
          )}
          {panel.messages.length > 0 && (
            <button
              onClick={handleClearContext}
              disabled={clearing}
              className={`flex items-center gap-1 px-1.5 py-1 rounded-md text-[10px] transition-colors ${
                confirmClear
                  ? 'bg-accent-red/20 text-accent-red'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
              }`}
              title={confirmClear ? '再次点击确认清除' : '清除上下文'}
            >
              {clearing ? (
                <span className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin block" />
              ) : (
                <Eraser size={11} />
              )}
              {confirmClear ? '确认清除' : '清除'}
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {panel.messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center gap-3 py-16">
            <div className="w-12 h-12 rounded-2xl bg-accent-blue/10 flex items-center justify-center">
              <Bot size={24} className="text-accent-blue/60" />
            </div>
            <div>
              <p className="text-text-secondary text-sm">准备就绪</p>
              <p className="text-text-secondary/50 text-xs mt-0.5">
                {panel.modelConfig.model}
              </p>
            </div>
          </div>
        ) : (
          panel.messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
