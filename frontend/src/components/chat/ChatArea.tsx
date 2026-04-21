import React, { useState, useEffect, useCallback } from 'react'
import { useChatStore } from '../../stores/chatStore'
import { ChatPanel } from './ChatPanel'
import { PanelDiffView } from './PanelDiffView'
import { MessageInput } from './MessageInput'
import { AttachmentWorkspace } from './AttachmentWorkspace'
import { SessionMemoryWorkspace } from './SessionMemoryWorkspace'
import { createSession, getSessionMessages } from '../../api/client'
import {
  GitCompare,
  Globe,
  Database,
  MessageSquare,
  Paperclip,
  FileText,
  X,
} from 'lucide-react'
import type { ActiveStreamControl } from './streamControl'

interface WelcomeGuideProps {
  webSearchEnabled: boolean
  knowledgeBaseEnabled: boolean
  onDismiss: () => void
  onEnableFocusChat: () => void
  onEnableDocAnalysis: () => void
  onEnableDeliveryMode: () => void
  onToggleWebSearch: () => void
  onToggleKnowledgeBase: () => void
}

const WelcomeGuide: React.FC<WelcomeGuideProps> = ({
  webSearchEnabled,
  knowledgeBaseEnabled,
  onDismiss,
  onEnableFocusChat,
  onEnableDocAnalysis,
  onEnableDeliveryMode,
  onToggleWebSearch,
  onToggleKnowledgeBase,
}) => (
  <div className="flex flex-1 items-center justify-center p-3 pt-2" data-testid="welcome-guide">
    <section className="relative w-full max-w-5xl rounded-[28px] border border-bg-border bg-gradient-to-br from-bg-secondary via-bg-secondary to-bg-primary p-5 shadow-[0_18px_70px_rgba(15,23,42,0.18)]">
      <button
        type="button"
        onClick={onDismiss}
        className="absolute right-4 top-4 inline-flex h-9 w-9 items-center justify-center rounded-full border border-bg-border bg-bg-primary/75 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
        aria-label="关闭新手引导"
        title="关闭新手引导"
      >
        <X size={16} />
      </button>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-accent-blue/20 bg-accent-blue/10 px-3 py-1 text-[11px] font-medium text-accent-blue">
            <span className="h-1.5 w-1.5 rounded-full bg-current" />
            先从一个最简单的动作开始
          </div>
          <h2 className="mt-4 text-2xl font-semibold tracking-tight text-text-primary sm:text-[2rem]">
            第一次使用时，你只需要决定一件事
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-text-secondary">
            直接开聊、带资料提问，或者先整理交付件。复杂能力都还在，但不需要一上来就全部理解。
          </p>

          <div className="mt-5 grid gap-3 md:grid-cols-3">
            <button
              type="button"
              onClick={onEnableFocusChat}
              data-testid="welcome-focus-chat"
              className="rounded-2xl border border-bg-border bg-bg-primary/70 p-4 text-left transition-colors hover:border-accent-blue/35 hover:bg-bg-hover"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-accent-blue/12 text-accent-blue">
                <MessageSquare size={18} />
              </div>
              <h3 className="mt-4 text-sm font-semibold text-text-primary">直接开聊</h3>
              <p className="mt-2 text-xs leading-5 text-text-secondary">
                插入一个结构化提问模板，先把问题聊清楚。
              </p>
            </button>

            <button
              type="button"
              onClick={onEnableDocAnalysis}
              data-testid="welcome-doc-analysis"
              className="rounded-2xl border border-bg-border bg-bg-primary/70 p-4 text-left transition-colors hover:border-accent-green/35 hover:bg-bg-hover"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-accent-green/12 text-accent-green">
                <Paperclip size={18} />
              </div>
              <h3 className="mt-4 text-sm font-semibold text-text-primary">带资料提问</h3>
              <p className="mt-2 text-xs leading-5 text-text-secondary">
                自动打开知识库语境，并给出适合上传文档后的分析模板。
              </p>
            </button>

            <button
              type="button"
              onClick={onEnableDeliveryMode}
              data-testid="welcome-delivery-mode"
              className="rounded-2xl border border-bg-border bg-bg-primary/70 p-4 text-left transition-colors hover:border-accent-orange/35 hover:bg-bg-hover"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-accent-orange/12 text-accent-orange">
                <FileText size={18} />
              </div>
              <h3 className="mt-4 text-sm font-semibold text-text-primary">先做成果</h3>
              <p className="mt-2 text-xs leading-5 text-text-secondary">
                生成演示稿、汇报 PPT 或结构化报告。对话后点工具栏“更多”→“生成演示稿”即可一键导出。
              </p>
            </button>
          </div>
        </div>

        <aside className="rounded-[24px] border border-bg-border bg-bg-primary/70 p-4">
          <div className="text-sm font-semibold text-text-primary">新手上手只记 3 件事</div>
          <div className="mt-3 space-y-3 text-xs leading-5 text-text-secondary">
            <div className="rounded-2xl bg-bg-secondary/70 px-3 py-3">
              <div className="font-medium text-text-primary">1. 先直接在下方输入框提问</div>
              <div className="mt-1">不用先配模型、Prompt 或工作区，先把问题问出来就行。</div>
            </div>
            <div className="rounded-2xl bg-bg-secondary/70 px-3 py-3">
              <div className="font-medium text-text-primary">2. 要带文件时，点输入框右侧回形针</div>
              <div className="mt-1">上传文档后再提问，系统会把附件一起带入本轮回答。</div>
            </div>
            <div className="rounded-2xl bg-bg-secondary/70 px-3 py-3">
              <div className="font-medium text-text-primary">3. 只有需要实时信息时再开联网</div>
              <div className="mt-1">平时保持简单模式，熟悉后再用多面板、记忆、任务中心这些进阶能力。</div>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onToggleWebSearch}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs transition-colors ${
                webSearchEnabled
                  ? 'bg-accent-blue/18 text-accent-blue'
                  : 'bg-bg-secondary text-text-secondary hover:text-text-primary'
              }`}
            >
              <Globe size={12} />
              联网 {webSearchEnabled ? '已开启' : '未开启'}
            </button>
            <button
              type="button"
              onClick={onToggleKnowledgeBase}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs transition-colors ${
                knowledgeBaseEnabled
                  ? 'bg-accent-green/18 text-accent-green'
                  : 'bg-bg-secondary text-text-secondary hover:text-text-primary'
              }`}
            >
              <Database size={12} />
              知识库 {knowledgeBaseEnabled ? '已开启' : '未开启'}
            </button>
          </div>
        </aside>
      </div>
    </section>
  </div>
)

export const ChatArea: React.FC = () => {
  const {
    panels,
    currentSessionId,
    currentWorkspaceId,
    attachmentWorkspaceOpen,
    memoryWorkspaceOpen,
    setAttachmentWorkspaceOpen,
    setMemoryWorkspaceOpen,
    welcomeGuideDismissed,
    setWelcomeGuideDismissed,
    webSearchEnabled,
    setWebSearchEnabled,
    knowledgeBaseEnabled,
    setKnowledgeBaseEnabled,
    clearMessages,
    addSession,
    setCurrentSession,
    adjustWorkspaceSessionCount,
    jumpTarget,
    pushComposerSeed,
  } = useChatStore()
  const [streamingPanels, setStreamingPanels] = useState<Set<string>>(new Set())
  const [streamingStartedAtByPanelId, setStreamingStartedAtByPanelId] = useState<Record<string, number>>({})
  const [streamingClock, setStreamingClock] = useState(() => Date.now())
  const [contextLimit, setContextLimit] = useState(16)
  const [activeStreamControl, setActiveStreamControl] = useState<ActiveStreamControl | null>(null)
  const [diffViewOpen, setDiffViewOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768)
  const [activeMobilePanelId, setActiveMobilePanelId] = useState('')
  const isAnyStreaming = streamingPanels.size > 0
  const hasAnyMessages = panels.some((panel) => panel.messages.length > 0)
  const showWelcomeGuide = !hasAnyMessages && !welcomeGuideDismissed

  useEffect(() => {
    if (!currentSessionId) return
    getSessionMessages(currentSessionId)
      .then(({ context_limit }) => setContextLimit(context_limit))
      .catch(() => {})
  }, [currentSessionId])

  // 全局键盘快捷键
  const handleKeyboardShortcut = useCallback(
    (e: KeyboardEvent) => {
      const ctrl = e.ctrlKey || e.metaKey
      if (!ctrl) return

      // Ctrl+/ 切换联网搜索
      if (e.key === '/') {
        e.preventDefault()
        setWebSearchEnabled(!webSearchEnabled)
        return
      }
      // Ctrl+Shift+S 切换知识库
      if (e.shiftKey && e.key === 'S') {
        e.preventDefault()
        setKnowledgeBaseEnabled(!knowledgeBaseEnabled)
        return
      }
      // Ctrl+K 新建对话
      if (e.key === 'k' || e.key === 'K') {
        e.preventDefault()
        if (isAnyStreaming) return
        createSession('新建对话', { workspace_id: currentWorkspaceId ?? undefined })
          .then((s) => {
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
          })
          .catch(() => {})
        return
      }
    },
    [
      webSearchEnabled,
      setWebSearchEnabled,
      knowledgeBaseEnabled,
      setKnowledgeBaseEnabled,
      isAnyStreaming,
      currentWorkspaceId,
      addSession,
      adjustWorkspaceSessionCount,
      setCurrentSession,
      clearMessages,
    ],
  )

  useEffect(() => {
    window.addEventListener('keydown', handleKeyboardShortcut)
    return () => window.removeEventListener('keydown', handleKeyboardShortcut)
  }, [handleKeyboardShortcut])

  useEffect(() => {
    if (panels.length <= 1 && diffViewOpen) {
      setDiffViewOpen(false)
    }
  }, [panels.length, diffViewOpen])

  useEffect(() => {
    if (!isAnyStreaming) return
    setStreamingClock(Date.now())
    const timer = window.setInterval(() => {
      setStreamingClock(Date.now())
    }, 1000)
    return () => window.clearInterval(timer)
  }, [isAnyStreaming])

  useEffect(() => {
    const media = window.matchMedia('(max-width: 767px)')

    const applyViewport = (matches: boolean) => {
      setIsMobile(matches)
      if (matches) {
        setDiffViewOpen(false)
      }
    }

    applyViewport(media.matches)

    const handleChange = (event: MediaQueryListEvent) => {
      applyViewport(event.matches)
    }

    media.addEventListener('change', handleChange)
    return () => media.removeEventListener('change', handleChange)
  }, [])

  useEffect(() => {
    if (panels.length === 0) {
      setActiveMobilePanelId('')
      return
    }
    if (!activeMobilePanelId || !panels.some((panel) => panel.id === activeMobilePanelId)) {
      setActiveMobilePanelId(panels[0].id)
    }
  }, [activeMobilePanelId, panels])

  useEffect(() => {
    if (
      isMobile &&
      jumpTarget?.role === 'assistant' &&
      jumpTarget.panelId &&
      panels.some((panel) => panel.id === jumpTarget.panelId)
    ) {
      setActiveMobilePanelId(jumpTarget.panelId)
    }
  }, [isMobile, jumpTarget, panels])

  const handleStreamingChange = (panelId: string, streaming: boolean) => {
    const now = Date.now()
    setStreamingClock(now)
    setStreamingPanels((prev) => {
      const next = new Set(prev)
      if (streaming) next.add(panelId)
      else next.delete(panelId)
      return next
    })
    setStreamingStartedAtByPanelId((prev) => {
      if (streaming) {
        if (typeof prev[panelId] === 'number') return prev
        return { ...prev, [panelId]: now }
      }
      if (!(panelId in prev)) return prev
      const next = { ...prev }
      delete next[panelId]
      return next
    })
  }

  const visiblePanels =
    isMobile && !diffViewOpen
      ? panels.filter((panel) => panel.id === activeMobilePanelId)
      : panels

  const seedComposer = (
    text: string,
    options?: {
      enableWebSearch?: boolean
      enableKnowledgeBase?: boolean
    },
  ) => {
    setWelcomeGuideDismissed(true)
    if (typeof options?.enableWebSearch === 'boolean') {
      setWebSearchEnabled(options.enableWebSearch)
    }
    if (typeof options?.enableKnowledgeBase === 'boolean') {
      setKnowledgeBaseEnabled(options.enableKnowledgeBase)
    }
    pushComposerSeed({ text })
  }

  return (
    <div className="relative flex flex-1 min-w-0 min-h-0">
      <div className="flex min-w-0 flex-1 flex-col">
        {!isMobile && !showWelcomeGuide && (
          <div className="flex items-center justify-end px-2 pt-2">
            <button
              type="button"
              onClick={() => setDiffViewOpen((value) => !value)}
              disabled={panels.length <= 1}
              className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs transition-colors ${
                diffViewOpen
                  ? 'bg-accent-blue/20 text-accent-blue'
                  : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
              } disabled:cursor-not-allowed disabled:opacity-40`}
              title={panels.length <= 1 ? '至少需要 2 个面板才能对比' : '切换多面板对比视图'}
            >
              <GitCompare size={13} />
              <span>{diffViewOpen ? '关闭对比' : '差异对比'}</span>
            </button>
          </div>
        )}

        <div className="flex flex-1 min-h-0 flex-col gap-2 overflow-y-auto p-2 pt-1 lg:flex-row lg:overflow-hidden">
          {showWelcomeGuide ? (
            <WelcomeGuide
              webSearchEnabled={webSearchEnabled}
              knowledgeBaseEnabled={knowledgeBaseEnabled}
              onDismiss={() => setWelcomeGuideDismissed(true)}
              onEnableFocusChat={() =>
                seedComposer(
                  '请先帮我理清这个问题，并按以下结构输出：\n1. 背景\n2. 关键判断\n3. 建议行动\n',
                )
              }
              onEnableDocAnalysis={() =>
                seedComposer(
                  '我接下来会上传资料，请先阅读资料，再按以下结构帮助我分析：\n1. 核心摘要\n2. 关键信息\n3. 风险或疑点\n4. 下一步建议\n',
                  { enableKnowledgeBase: true },
                )
              }
              onEnableDeliveryMode={() =>
                seedComposer(
                  '请先帮我整理一份汇报提纲，按以下结构输出：\n1. 结论先行\n2. 证据与依据\n3. 建议的页面结构\n4. 还缺哪些信息\n',
                  { enableKnowledgeBase: true },
                )
              }
              onToggleWebSearch={() => setWebSearchEnabled(!webSearchEnabled)}
              onToggleKnowledgeBase={() => setKnowledgeBaseEnabled(!knowledgeBaseEnabled)}
            />
          ) : diffViewOpen ? (
            <PanelDiffView panels={panels} />
          ) : (
            visiblePanels.map((panel) => (
              <ChatPanel
                key={panel.id}
                panel={panel}
                isStreaming={streamingPanels.has(panel.id)}
                loadingElapsedMs={
                  streamingPanels.has(panel.id)
                    ? Math.max(
                        0,
                        streamingClock - (streamingStartedAtByPanelId[panel.id] ?? streamingClock),
                      )
                    : 0
                }
                isInteractionLocked={isAnyStreaming}
                activeStreamControl={activeStreamControl}
                setActiveStreamControl={setActiveStreamControl}
                contextLimit={contextLimit}
                onStreamingChange={handleStreamingChange}
              />
            ))
          )}
        </div>

        {isMobile && panels.length > 1 && !diffViewOpen && !showWelcomeGuide && (
          <div className="border-t border-bg-border bg-bg-secondary/95 px-2 py-2">
            <div className="flex gap-2 overflow-x-auto pb-1">
              {panels.map((panel, index) => {
                const active = panel.id === activeMobilePanelId
                return (
                  <button
                    key={panel.id}
                    type="button"
                    onClick={() => setActiveMobilePanelId(panel.id)}
                    className={`min-w-[110px] rounded-xl border px-3 py-2 text-left text-xs transition-colors ${
                      active
                        ? 'border-accent-blue/40 bg-accent-blue/15 text-accent-blue'
                        : 'border-bg-border bg-bg-primary text-text-secondary'
                    }`}
                  >
                    <div className="font-semibold">面板 {index + 1}</div>
                    <div className="mt-1 truncate text-[11px] opacity-80">
                      {panel.modelConfig.model || '默认模型'}
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        )}

        <MessageInput
          onStreamingChange={handleStreamingChange}
          isInteractionLocked={isAnyStreaming}
          activeStreamControl={activeStreamControl}
          setActiveStreamControl={setActiveStreamControl}
        />
      </div>

      <AttachmentWorkspace
        open={attachmentWorkspaceOpen}
        interactionLocked={isAnyStreaming}
        onClose={() => setAttachmentWorkspaceOpen(false)}
      />
      <SessionMemoryWorkspace
        open={memoryWorkspaceOpen}
        interactionLocked={isAnyStreaming}
        onClose={() => setMemoryWorkspaceOpen(false)}
      />
    </div>
  )
}
