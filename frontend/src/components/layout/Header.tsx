import React, { useEffect, useState } from 'react'
import {
  Check,
  PanelLeftOpen,
  Plus,
  Minus,
  Globe,
  History,
  Menu,
  Monitor,
  MoreHorizontal,
  Settings,
  SquarePen,
  UserCog,
  FileText,
  Paperclip,
  RotateCcw,
  Database,
  Brain,
  Moon,
  Sun,
  Share2,
} from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import { useResolvedTheme } from '../../hooks/useResolvedTheme'
import { Button } from '../ui/Button'
import { InlineNotice } from '../ui/InlineNotice'
import { createDeckDraft, createSession, createSessionShareLink, getSystemPrompts, resetSession } from '../../api/client'
import { DeckEditorModal } from '../reports/DeckEditorModal'
import { DeckGenerationModal } from '../reports/DeckGenerationModal'
import { TaskCenterModal } from '../tasks/TaskCenterModal'
import { KnowledgeBaseModal } from '../settings/KnowledgeBaseModal'
import { Modal } from '../ui/Modal'
import type { DeckSpec, SystemPrompt } from '../../api/client'

export const Header: React.FC = () => {
  const {
    sidebarOpen,
    toggleSidebar,
    panels,
    addPanel,
    removePanel,
    webSearchEnabled,
    setWebSearchEnabled,
    knowledgeBaseEnabled,
    setKnowledgeBaseEnabled,
    addSession,
    setCurrentSession,
    clearMessages,
    updateSession,
    attachmentWorkspaceOpen,
    toggleAttachmentWorkspace,
    memoryWorkspaceOpen,
    toggleMemoryWorkspace,
    setSettingsOpen,
    setWelcomeGuideDismissed,
    setTheme,
    activePromptId,
    currentSessionId,
    currentWorkspaceId,
    adjustWorkspaceSessionCount,
  } = useChatStore()

  const { theme, resolvedTheme } = useResolvedTheme()
  const toggleTheme = useChatStore((s) => s.toggleTheme)
  const [activePrompt, setActivePrompt] = useState<SystemPrompt | null>(null)
  const [deckConfigOpen, setDeckConfigOpen] = useState(false)
  const [deckOpen, setDeckOpen] = useState(false)
  const [deckData, setDeckData] = useState<DeckSpec | null>(null)
  const [generatingDeck, setGeneratingDeck] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [resetConfirm, setResetConfirm] = useState(false)
  const [taskCenterOpen, setTaskCenterOpen] = useState(false)
  const [kbManageOpen, setKbManageOpen] = useState(false)
  const [sharingSession, setSharingSession] = useState(false)
  const [sessionShareCopied, setSessionShareCopied] = useState(false)
  const [actionFeedback, setActionFeedback] = useState<{
    tone: 'error' | 'success'
    message: string
  } | null>(null)
  const [moreMenuOpen, setMoreMenuOpen] = useState(false)
  const moreMenuRef = React.useRef<HTMLDivElement>(null)
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768)
  const [mobileActionsOpen, setMobileActionsOpen] = useState(false)
  const hasAnyMessages = panels.some((panel) => panel.messages.length > 0)
  const showAdvancedDesktopActions = hasAnyMessages

  useEffect(() => {
    getSystemPrompts()
      .then((list) => {
        const active = list.find((p) => p.is_active) ?? list[0] ?? null
        setActivePrompt(active)
      })
      .catch(() => {})
  }, [activePromptId])

  useEffect(() => {
    if (!moreMenuOpen) return
    const handleClickOutside = (e: MouseEvent) => {
      if (moreMenuRef.current && !moreMenuRef.current.contains(e.target as Node)) {
        setMoreMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [moreMenuOpen])

  useEffect(() => {
    const media = window.matchMedia('(max-width: 767px)')

    const applyViewport = (matches: boolean) => {
      setIsMobile(matches)
      if (!matches) {
        setMobileActionsOpen(false)
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
    if (!actionFeedback) return
    const timer = window.setTimeout(() => setActionFeedback(null), 3200)
    return () => window.clearTimeout(timer)
  }, [actionFeedback])

  const handleNewChat = async () => {
    try {
      const s = await createSession('新建对话', {
        workspace_id: currentWorkspaceId ?? undefined,
      })
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
    } catch {
      // sidebar will show error
    }
  }

  const handleGenerateReport = async () => {
    if (!currentSessionId || generatingDeck) return
    setDeckConfigOpen(true)
  }

  const handleAddPanel = () => {
    setWelcomeGuideDismissed(true)
    addPanel()
  }

  const handleRemovePanel = () => {
    if (panels.length <= 1) return
    removePanel(panels[panels.length - 1].id)
  }

  const handleGenerateDeck = async (payload: {
    panel_config: (typeof panels)[number]['modelConfig']
    target_slide_count: number
    theme: 'default' | 'midnight' | 'sunrise'
  }) => {
    if (!currentSessionId) return
    setGeneratingDeck(true)
    try {
      const data = await createDeckDraft({
        session_id: currentSessionId,
        panel_config: payload.panel_config,
        knowledge_base_enabled: knowledgeBaseEnabled,
        target_slide_count: payload.target_slide_count,
        theme: payload.theme,
      })
      setDeckData(data)
      setDeckOpen(true)
      setActionFeedback(null)
    } catch (e) {
      setActionFeedback({
        tone: 'error',
        message: `生成演示稿失败：${(e as Error).message}`,
      })
    } finally {
      setGeneratingDeck(false)
    }
  }

  const handleResetSession = async () => {
    if (!resetConfirm) {
      setResetConfirm(true)
      setTimeout(() => setResetConfirm(false), 3000)
      return
    }
    if (!currentSessionId) return
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
    } catch (e) {
      setActionFeedback({
        tone: 'error',
        message: `重置会话失败：${(e as Error).message}`,
      })
    } finally {
      setResetting(false)
    }
  }

  const handleShareSession = async () => {
    if (!currentSessionId || sharingSession) return
    setSharingSession(true)
    try {
      const payload = await createSessionShareLink(currentSessionId)
      await navigator.clipboard.writeText(payload.share_url)
      setSessionShareCopied(true)
      setActionFeedback({
        tone: 'success',
        message: '分享链接已复制到剪贴板。',
      })
      window.setTimeout(() => setSessionShareCopied(false), 2000)
    } catch (e) {
      setActionFeedback({
        tone: 'error',
        message: `创建分享链接失败：${(e as Error).message}`,
      })
    } finally {
      setSharingSession(false)
    }
  }

  const kbStatus = activePrompt?.vector_store_id ? 'bound' : 'default'
  const themeLabel =
    theme === 'dark' ? '深色' : theme === 'light' ? '浅色' : '跟随系统'
  const themeIcon =
    theme === 'dark' ? <Sun size={15} /> : theme === 'light' ? <Moon size={15} /> : <Monitor size={15} />
  const mobileQuickActions = [
    {
      key: 'web',
      label: '联网',
      icon: <Globe size={13} />,
      active: webSearchEnabled,
      onClick: () => setWebSearchEnabled(!webSearchEnabled),
      activeClass: 'bg-accent-blue/20 text-accent-blue',
    },
    {
      key: 'kb',
      label: '知识库',
      icon: <Database size={13} />,
      active: knowledgeBaseEnabled,
      onClick: () => setKnowledgeBaseEnabled(!knowledgeBaseEnabled),
      activeClass: 'bg-accent-green/20 text-accent-green',
    },
    {
      key: 'attachment',
      label: '附件',
      icon: <Paperclip size={13} />,
      active: attachmentWorkspaceOpen,
      onClick: () => currentSessionId && toggleAttachmentWorkspace(),
      disabled: !currentSessionId,
      activeClass: 'bg-accent-blue/20 text-accent-blue',
    },
    {
      key: 'memory',
      label: '记忆',
      icon: <Brain size={13} />,
      active: memoryWorkspaceOpen,
      onClick: () => currentSessionId && toggleMemoryWorkspace(),
      disabled: !currentSessionId,
      activeClass: 'bg-accent-green/20 text-accent-green',
    },
  ]

  return (
    <>
      <header className="sticky top-0 z-20 shrink-0 border-b border-bg-border bg-bg-primary/95 backdrop-blur-sm">
        {isMobile ? (
          <>
            <div className="flex items-center justify-between gap-2 px-3 py-2">
              <div className="flex min-w-0 items-center gap-2">
                <button
                  onClick={toggleSidebar}
                  className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                  title="展开侧边栏"
                >
                  <PanelLeftOpen size={16} />
                </button>
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-text-primary">
                    {activePrompt?.name || 'AI 工作台'}
                  </div>
                  <div className="text-[11px] text-text-secondary">
                    {panels.length} 个面板 · {resolvedTheme === 'dark' ? '深色模式' : '浅色模式'}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-1">
                <button
                  onClick={handleNewChat}
                  className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                  title="新建对话"
                >
                  <SquarePen size={15} />
                </button>
                <button
                  onClick={toggleTheme}
                  className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                  title={`当前主题: ${themeLabel}`}
                >
                  {themeIcon}
                </button>
                <button
                  onClick={() => setMobileActionsOpen(true)}
                  className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                  title="更多操作"
                >
                  <Menu size={16} />
                </button>
              </div>
            </div>

            <div className="overflow-x-auto px-3 pb-2">
              <div className="flex gap-2">
                {mobileQuickActions.map((action) => (
                  <button
                    key={action.key}
                    onClick={action.onClick}
                    disabled={action.disabled}
                    className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs transition-colors ${
                      action.active
                        ? action.activeClass
                        : 'bg-bg-secondary text-text-secondary hover:text-text-primary'
                    } disabled:opacity-40`}
                  >
                    {action.icon}
                    <span>{action.label}</span>
                  </button>
                ))}
              </div>
            </div>
          </>
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 sm:px-4">
            <div className="flex min-w-0 items-center gap-2">
              {!sidebarOpen && (
                <button
                  onClick={toggleSidebar}
                  className="hidden rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary md:flex"
                  title="展开侧边栏"
                >
                  <PanelLeftOpen size={16} />
                </button>
              )}
              <span className="whitespace-nowrap text-xs text-text-secondary">
                {panels.length} 个面板
              </span>
              {activePrompt && (
                <button
                  onClick={() => setSettingsOpen(true)}
                  className="hidden min-w-0 items-center gap-1 rounded-lg border border-bg-border px-2 py-1 text-[10px] text-text-secondary/70 transition-colors hover:bg-bg-hover hover:text-text-primary sm:flex"
                  title="当前角色"
                >
                  <UserCog size={11} />
                  <span className="truncate">{activePrompt.name}</span>
                  {kbStatus === 'bound' && (
                    <span title="已绑定知识库">
                      <Database size={9} className="ml-0.5 text-accent-green" />
                    </span>
                  )}
                </button>
              )}
            </div>

            <div className="order-3 flex w-full items-center justify-center gap-1.5 sm:order-2 sm:w-auto">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRemovePanel}
                disabled={panels.length <= 1}
                title="减少面板"
              >
                <Minus size={13} />
              </Button>
              <span className="w-4 text-center text-xs text-text-secondary">{panels.length}</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleAddPanel}
                disabled={panels.length >= 6}
                title="增加面板"
              >
                <Plus size={13} />
              </Button>
              </div>

            <div className="order-2 ml-auto flex flex-wrap items-center justify-end gap-1.5 sm:order-3 sm:ml-0">
              <button
                onClick={() => setWebSearchEnabled(!webSearchEnabled)}
                className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs transition-colors ${
                  webSearchEnabled
                    ? 'bg-accent-blue/20 text-accent-blue'
                    : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                }`}
                title="联网搜索"
              >
                <Globe size={13} />
                <span className="hidden sm:inline">联网</span>
              </button>

              <div className="flex items-center gap-0.5">
                <button
                  onClick={() => setKnowledgeBaseEnabled(!knowledgeBaseEnabled)}
                  className={`flex items-center gap-1.5 rounded-l-lg px-2.5 py-1.5 text-xs transition-colors ${
                    knowledgeBaseEnabled
                      ? 'bg-accent-green/20 text-accent-green'
                      : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                  }`}
                  title="知识库开关"
                >
                  <Database size={13} />
                  <span className="hidden sm:inline">知识库</span>
                </button>
                <button
                  onClick={() => setKbManageOpen(true)}
                  className="flex items-center rounded-r-lg border-l border-bg-border px-1.5 py-1.5 text-xs text-text-muted transition-colors hover:bg-bg-hover hover:text-text-primary"
                  title="管理知识库"
                >
                  <Settings size={11} />
                </button>
              </div>

              {showAdvancedDesktopActions && (
                <>
              <button
                onClick={toggleAttachmentWorkspace}
                disabled={!currentSessionId}
                className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs transition-colors ${
                  attachmentWorkspaceOpen
                    ? 'bg-accent-blue/20 text-accent-blue'
                    : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                } disabled:opacity-40`}
                title="附件工作区"
              >
                <Paperclip size={13} />
                <span className="hidden sm:inline">附件</span>
              </button>

              <button
                onClick={toggleMemoryWorkspace}
                disabled={!currentSessionId}
                className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs transition-colors ${
                  memoryWorkspaceOpen
                    ? 'bg-accent-green/20 text-accent-green'
                    : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                } disabled:opacity-40`}
                title="记忆工作区"
              >
                <Brain size={13} />
                <span className="hidden sm:inline">记忆</span>
              </button>

              {/* 更多操作下拉菜单 */}
              <div className="relative" ref={moreMenuRef}>
                <button
                  onClick={() => setMoreMenuOpen((v) => !v)}
                  className={`rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary ${
                    moreMenuOpen ? 'bg-bg-hover text-text-primary' : ''
                  }`}
                  title="更多操作"
                >
                  <MoreHorizontal size={15} />
                </button>
                {moreMenuOpen && (
                  <div className="absolute right-0 top-full z-30 mt-1 min-w-[160px] overflow-hidden rounded-xl border border-bg-border bg-bg-primary shadow-xl">
                    <button
                      onClick={() => { void handleShareSession(); setMoreMenuOpen(false) }}
                      disabled={!currentSessionId || sharingSession}
                      className="flex w-full items-center gap-2 px-3 py-2 text-xs text-text-primary transition-colors hover:bg-bg-hover disabled:opacity-40"
                    >
                      {sessionShareCopied ? <Check size={13} className="text-accent-green" /> : <Share2 size={13} />}
                      {sessionShareCopied ? '已复制链接' : '分享会话'}
                    </button>
                    <button
                      onClick={() => { void handleGenerateReport(); setMoreMenuOpen(false) }}
                      disabled={generatingDeck || !currentSessionId}
                      className="flex w-full items-center gap-2 px-3 py-2 text-xs text-text-primary transition-colors hover:bg-bg-hover disabled:opacity-40"
                    >
                      <FileText size={13} />
                      生成演示稿
                    </button>
                    <button
                      onClick={() => { setTaskCenterOpen(true); setMoreMenuOpen(false) }}
                      className="flex w-full items-center gap-2 px-3 py-2 text-xs text-text-primary transition-colors hover:bg-bg-hover"
                    >
                      <History size={13} />
                      任务中心
                    </button>
                    <div className="mx-2 border-t border-bg-border" />
                    <button
                      onClick={() => { void handleResetSession(); setMoreMenuOpen(false) }}
                      disabled={resetting || !currentSessionId}
                      className={`flex w-full items-center gap-2 px-3 py-2 text-xs transition-colors hover:bg-bg-hover disabled:opacity-40 ${
                        resetConfirm ? 'text-accent-red' : 'text-text-primary'
                      }`}
                    >
                      <RotateCcw size={13} />
                      {resetConfirm ? '确认重置？' : '重置会话'}
                    </button>
                  </div>
                )}
              </div>
                </>
              )}

              <button
                onClick={handleNewChat}
                className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                title="新建对话"
              >
                <SquarePen size={15} />
              </button>
              <button
                onClick={toggleTheme}
                className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                title={`当前主题: ${themeLabel}`}
              >
                {themeIcon}
              </button>
              <button
                onClick={() => setSettingsOpen(true)}
                className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                title="设置"
              >
                <Settings size={15} />
              </button>
            </div>
          </div>
        )}
      </header>

      {actionFeedback && (
        <div className="px-3 pt-2 sm:px-4">
          <InlineNotice message={actionFeedback.message} tone={actionFeedback.tone} />
        </div>
      )}

      <Modal open={mobileActionsOpen} onClose={() => setMobileActionsOpen(false)} title="快捷操作" width="max-w-md">
        <div className="space-y-4">
          <div>
            <div className="mb-2 text-xs font-medium text-text-secondary">布局与工具</div>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => {
                  handleAddPanel()
                  setMobileActionsOpen(false)
                }}
                disabled={panels.length >= 6}
                className="rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-hover disabled:opacity-40"
              >
                增加面板
              </button>
              <button
                onClick={() => {
                  handleRemovePanel()
                  setMobileActionsOpen(false)
                }}
                disabled={panels.length <= 1}
                className="rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-hover disabled:opacity-40"
              >
                减少面板
              </button>
              <button
                onClick={() => {
                  setTaskCenterOpen(true)
                  setMobileActionsOpen(false)
                }}
                className="rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-hover"
              >
                任务中心
              </button>
              <button
                onClick={() => {
                  setKbManageOpen(true)
                  setMobileActionsOpen(false)
                }}
                className="rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-hover"
              >
                知识库管理
              </button>
              <button
                onClick={() => {
                  setSettingsOpen(true)
                  setMobileActionsOpen(false)
                }}
                className="rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-hover"
              >
                设置
              </button>
            </div>
          </div>

          <div>
            <div className="mb-2 text-xs font-medium text-text-secondary">会话操作</div>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => {
                  void handleShareSession()
                  setMobileActionsOpen(false)
                }}
                disabled={!currentSessionId || sharingSession}
                className="rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-hover disabled:opacity-40"
              >
                {sessionShareCopied ? '已复制链接' : '分享会话'}
              </button>
              <button
                onClick={() => {
                  void handleGenerateReport()
                  setMobileActionsOpen(false)
                }}
                disabled={!currentSessionId || generatingDeck}
                className="rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-hover disabled:opacity-40"
              >
                生成演示稿
              </button>
              <button
                onClick={() => {
                  void handleResetSession()
                  setMobileActionsOpen(false)
                }}
                disabled={!currentSessionId || resetting}
                className="rounded-xl border border-accent-red/20 bg-bg-primary px-3 py-2 text-sm text-accent-red transition-colors hover:bg-accent-red/5 disabled:opacity-40"
              >
                {resetConfirm ? '确认重置？' : '重置会话'}
              </button>
              <button
                onClick={() => {
                  void handleNewChat()
                  setMobileActionsOpen(false)
                }}
                className="rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-hover"
              >
                新建对话
              </button>
            </div>
          </div>

          <div>
            <div className="mb-2 text-xs font-medium text-text-secondary">主题</div>
            <div className="grid grid-cols-3 gap-2">
              {([
                ['dark', '深色'],
                ['light', '浅色'],
                ['system', '跟随系统'],
              ] as const).map(([value, label]) => (
                <button
                  key={value}
                  onClick={() => setTheme(value)}
                  className={`rounded-xl border px-3 py-2 text-sm transition-colors ${
                    theme === value
                      ? 'border-accent-blue/40 bg-accent-blue/15 text-accent-blue'
                      : 'border-bg-border bg-bg-primary text-text-primary hover:bg-bg-hover'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </Modal>

      <DeckGenerationModal
        open={deckConfigOpen}
        onClose={() => setDeckConfigOpen(false)}
        panels={panels}
        knowledgeBaseEnabled={knowledgeBaseEnabled}
        onSubmit={handleGenerateDeck}
      />

      {deckData && (
        <DeckEditorModal
          open={deckOpen}
          onClose={() => setDeckOpen(false)}
          deck={deckData}
          panels={panels}
          onDeckChange={setDeckData}
        />
      )}

      <TaskCenterModal open={taskCenterOpen} onClose={() => setTaskCenterOpen(false)} />
      <KnowledgeBaseModal open={kbManageOpen} onClose={() => setKbManageOpen(false)} />
    </>
  )
}
