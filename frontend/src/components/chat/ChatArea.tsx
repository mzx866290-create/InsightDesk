import React, { useState, useEffect } from 'react'
import { useChatStore } from '../../stores/chatStore'
import { ChatPanel } from './ChatPanel'
import { MessageInput } from './MessageInput'
import { getSessionMessages } from '../../api/client'

export const ChatArea: React.FC = () => {
  const { panels, currentSessionId } = useChatStore()
  const [streamingPanels, setStreamingPanels] = useState<Set<string>>(new Set())
  const [contextLimit, setContextLimit] = useState(16)

  useEffect(() => {
    if (!currentSessionId) return
    getSessionMessages(currentSessionId)
      .then(({ context_limit }) => setContextLimit(context_limit))
      .catch(() => {})
  }, [currentSessionId])

  const handleStreamingChange = (panelId: string, streaming: boolean) => {
    setStreamingPanels((prev) => {
      const next = new Set(prev)
      if (streaming) next.add(panelId)
      else next.delete(panelId)
      return next
    })
  }

  return (
    <div className="flex flex-col flex-1 min-w-0 min-h-0">
      {/* Panels */}
      <div className="flex flex-1 min-h-0 flex-col gap-2 overflow-y-auto p-2 lg:flex-row lg:overflow-hidden">
        {panels.map((panel) => (
          <ChatPanel
            key={panel.id}
            panel={panel}
            isStreaming={streamingPanels.has(panel.id)}
            contextLimit={contextLimit}
          />
        ))}
      </div>

      {/* Shared input */}
      <MessageInput onStreamingChange={handleStreamingChange} />
    </div>
  )
}
