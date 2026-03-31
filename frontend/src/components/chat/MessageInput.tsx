import React, { useRef, useState } from 'react'
import { Send, Globe, Square } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import { streamChat, createSession as apiCreateSession } from '../../api/client'
import type { SSEChunk } from '../../api/client'
import { useTaskStore } from '../../stores/taskStore'

interface MessageInputProps {
  onStreamingChange: (panelId: string, streaming: boolean) => void
}

export const MessageInput: React.FC<MessageInputProps> = ({ onStreamingChange }) => {
  const {
    panels,
    currentSessionId,
    webSearchEnabled,
    setWebSearchEnabled,
    addUserMessage,
    appendChunk,
    setAssistantMessage,
    setSources,
    setTaskId,
    addErrorMessage,
    addSession,
    setCurrentSession,
    updateSessionTitle,
    sessions,
  } = useChatStore()

  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const streamingMsgIds = useRef<Map<string, string>>(new Map())

  const adjustHeight = () => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 180) + 'px'
  }

  const handleStop = () => {
    abortControllerRef.current?.abort()
    setIsLoading(false)
    panels.forEach((p) => {
      const msgId = streamingMsgIds.current.get(p.id)
      if (msgId) {
        setAssistantMessage(p.id, msgId, '', false)
      }
      onStreamingChange(p.id, false)
    })
    streamingMsgIds.current.clear()
  }

  const handleSend = async () => {
    const msg = input.trim()
    if (!msg || isLoading) return

    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
    setIsLoading(true)

    // Ensure we have a session
    let sessionId = currentSessionId
    if (!sessionId) {
      try {
        const s = await apiCreateSession(msg.slice(0, 40))
        sessionId = s.session_id
        setCurrentSession(sessionId)
        addSession({
          session_id: sessionId,
          title: s.title,
          created_at: Date.now() / 1000,
          updated_at: Date.now() / 1000,
          message_count: 0,
        })
      } catch (e) {
        console.error('Failed to create session', e)
        setIsLoading(false)
        return
      }
    }

    // Add user message to all panels
    const userMsgId = addUserMessage(msg)
    void userMsgId

    // Update session title if it's the first message
    const currentSession = sessions.find((s) => s.session_id === sessionId)
    if (currentSession && currentSession.message_count === 0) {
      updateSessionTitle(sessionId, msg.slice(0, 40))
    }

    // Start streaming
    panels.forEach((p) => onStreamingChange(p.id, true))
    const assistantMsgIds = new Map<string, string>()
    panels.forEach((p) => {
      const id = `assistant-${p.id}-${Date.now()}`
      assistantMsgIds.set(p.id, id)
      streamingMsgIds.current.set(p.id, id)
    })

    const donePanels = new Set<string>()

    const controller = streamChat(
      sessionId,
      msg,
      panels.map((p) => p.modelConfig),
      webSearchEnabled,
      (chunk: SSEChunk) => {
        const msgId = assistantMsgIds.get(chunk.panel_id)
        if (!msgId) return

        if (chunk.type === 'chunk' && chunk.content) {
          appendChunk(chunk.panel_id, msgId, chunk.content)
        } else if (chunk.type === 'sources' && chunk.sources) {
          setSources(chunk.panel_id, msgId, chunk.sources)
        } else if (chunk.type === 'task_created' && chunk.task_id) {
          // Register task in store and start polling
          const taskStore = useTaskStore.getState()
          taskStore.addTask({
            task_id: chunk.task_id,
            task_type: chunk.task_type ?? 'task',
            status: 'pending',
            progress: 0,
            created_at: Date.now() / 1000,
            updated_at: Date.now() / 1000,
          })
          taskStore.startPolling(chunk.task_id)
          // Attach task info to the assistant message in this panel
          if (msgId) setTaskId(chunk.panel_id, msgId, chunk.task_id, chunk.task_type)
        } else if (chunk.type === 'done') {
          onStreamingChange(chunk.panel_id, false)
          donePanels.add(chunk.panel_id)
          if (donePanels.size === panels.length) {
            setIsLoading(false)
          }
        } else if (chunk.type === 'error') {
          // Mark the incomplete streaming message as done first
          setAssistantMessage(chunk.panel_id, msgId, '', false)
          // Add a structured error message
          addErrorMessage(
            chunk.panel_id,
            chunk.content ?? '请求处理时发生错误',
            chunk.error_code,
            chunk.suggestion,
          )
          onStreamingChange(chunk.panel_id, false)
          donePanels.add(chunk.panel_id)
          if (donePanels.size === panels.length) {
            setIsLoading(false)
          }
        }
      },
      () => {
        setIsLoading(false)
        panels.forEach((p) => onStreamingChange(p.id, false))
        streamingMsgIds.current.clear()
      },
      (err) => {
        // Network-level error: show in all panels
        panels.forEach((p) => {
          addErrorMessage(
            p.id,
            '网络连接失败，无法连接到服务器',
            'NETWORK_ERROR',
            '请检查网络连接或后端服务是否正常运行',
          )
          onStreamingChange(p.id, false)
        })
        setIsLoading(false)
        streamingMsgIds.current.clear()
        console.error('Stream error:', err)
      },
    )

    abortControllerRef.current = controller
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="border-t border-bg-border bg-bg-primary px-4 py-3 shrink-0">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-end gap-2 bg-bg-secondary border border-bg-border rounded-2xl px-4 py-3 focus-within:border-accent-blue/50 transition-colors">
          <textarea
            ref={textareaRef}
            className="flex-1 bg-transparent text-text-primary placeholder-text-secondary text-sm resize-none outline-none leading-relaxed min-h-[24px] max-h-[180px]"
            placeholder="输入消息… (Enter 发送，Shift+Enter 换行)"
            value={input}
            onChange={(e) => { setInput(e.target.value); adjustHeight() }}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={isLoading}
          />

          <div className="flex items-center gap-2 pb-0.5">
            {/* Web search toggle */}
            <button
              onClick={() => setWebSearchEnabled(!webSearchEnabled)}
              className={`flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs transition-colors ${
                webSearchEnabled
                  ? 'bg-accent-blue/20 text-accent-blue'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
              }`}
              title="联网搜索"
            >
              <Globe size={13} />
            </button>

            {/* Send / Stop button */}
            {isLoading ? (
              <button
                onClick={handleStop}
                className="w-8 h-8 flex items-center justify-center rounded-xl bg-accent-red/20 text-accent-red hover:bg-accent-red/30 transition-colors"
                title="停止生成"
              >
                <Square size={13} fill="currentColor" />
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                className="w-8 h-8 flex items-center justify-center rounded-xl bg-accent-blue disabled:opacity-30 disabled:cursor-not-allowed hover:bg-accent-blue-hover transition-colors text-white"
                title="发送 (Enter)"
              >
                <Send size={13} />
              </button>
            )}
          </div>
        </div>

        <div className="flex items-center justify-center mt-2 text-[10px] text-text-secondary/50">
          AI 可能出错，请独立核实重要信息
        </div>
      </div>
    </div>
  )
}
