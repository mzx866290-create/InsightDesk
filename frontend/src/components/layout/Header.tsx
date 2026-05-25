import React, { useEffect, useRef, useState } from 'react'
import {
  PanelLeftOpen,
  Plus,
  Minus,
  Globe,
  Menu,
  Monitor,
  Settings,
  SquarePen,
  UserCog,
  Paperclip,
  Database,
  Brain,
  Moon,
  Sun,
} from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import { useResolvedTheme } from '../../hooks/useResolvedTheme'
import { useI18n } from '../../i18n'
import { Button } from '../ui/Button'
import { InlineNotice } from '../ui/InlineNotice'
import { createSession, createSessionShareLink, getDeck, resetSession } from '../../api/client'
import { DeckEditorModal } from '../reports/DeckEditorModal'
import { DeckGenerationModal } from '../reports/DeckGenerationModal'
import { TaskProgressCard } from '../cards/TaskProgressCard'
import { TaskCenterModal } from '../tasks/TaskCenterModal'
import { KnowledgeBaseModal } from '../settings/KnowledgeBaseModal'
import type { DeckSpec } from '../../api/client'
import { createAndTrackTask, useTaskStore } from '../../stores/taskStore'
import { AssistantPresetSelector } from '../chat/AssistantPresetSelector'
import { HeaderMobileActionsModal } from './header/HeaderMobileActionsModal'
import { HeaderMoreMenu } from './header/HeaderMoreMenu'
import { useHeaderActivePrompt } from './header/useHeaderActivePrompt'
import { useHeaderViewport } from './header/useHeaderViewport'

export const Header: React.FC = () => {
  const {
    sidebarOpen,
    toggleSidebar,
    workspaces,
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
  const currentWorkspace =
    workspaces.find((workspace) => workspace.workspace_id === currentWorkspaceId) ?? null
  const toggleTheme = useChatStore((s) => s.toggleTheme)
  const { language, toggleLanguage, t } = useI18n()
  const [deckTaskId, setDeckTaskId] = useState<string | null>(null)
  const [handledDeckTaskId, setHandledDeckTaskId] = useState<string | null>(null)
  const deckTask = useTaskStore((s) => (deckTaskId ? s.tasks[deckTaskId] : undefined))
  const activePrompt = useHeaderActivePrompt(activePromptId)
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
  const moreMenuRef = useRef<HTMLDivElement>(null)
  const isMobile = useHeaderViewport()
  const [mobileActionsOpen, setMobileActionsOpen] = useState(false)
  const hasAnyMessages = panels.some((panel) => panel.messages.length > 0)
  const showAdvancedDesktopActions = hasAnyMessages
  const isDeckTaskActive = deckTask?.status === 'pending' || deckTask?.status === 'running'

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
    if (!isMobile) {
      setMobileActionsOpen(false)
    }
  }, [isMobile])

  useEffect(() => {
    if (!actionFeedback) return
    const timer = window.setTimeout(() => setActionFeedback(null), 3200)
    return () => window.clearTimeout(timer)
  }, [actionFeedback])

  useEffect(() => {
    if (!deckTaskId || !deckTask || handledDeckTaskId === deckTaskId) return

    if (deckTask.status === 'completed') {
      const nextDeckId =
        typeof deckTask.params?.deck_id === 'string' ? deckTask.params.deck_id : ''
      if (!nextDeckId) {
        setActionFeedback({
          tone: 'error',
          message: 'Deck 任务已完成，但没有返回可打开的 deck_id。',
        })
        setHandledDeckTaskId(deckTaskId)
        return
      }

      void getDeck(nextDeckId)
        .then((deck) => {
          setDeckData(deck)
          setDeckOpen(true)
          setActionFeedback(null)
          setHandledDeckTaskId(deckTaskId)
        })
        .catch((error) => {
          setActionFeedback({
            tone: 'error',
            message: `打开生成后的 Deck 失败：${(error as Error).message}`,
          })
          setHandledDeckTaskId(deckTaskId)
        })
      return
    }

    if (deckTask.status === 'failed') {
      setActionFeedback({
        tone: 'error',
        message: deckTask.error || '生成演示稿失败，请稍后重试。',
      })
      setHandledDeckTaskId(deckTaskId)
    }
  }, [deckTask, deckTaskId, handledDeckTaskId])

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
    if (!currentSessionId || generatingDeck || isDeckTaskActive) return
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
    template_id?: string
    template_options?: Record<string, unknown>
  }) => {
    if (!currentSessionId) return
    setGeneratingDeck(true)
    try {
      const task = await createAndTrackTask(
        'generate_deck',
        {
          panel_config: payload.panel_config,
          knowledge_base_enabled: knowledgeBaseEnabled,
          target_slide_count: payload.target_slide_count,
          theme: payload.theme,
          template_id: payload.template_id,
          template_options: payload.template_options,
        },
        currentSessionId,
      )
      setDeckTaskId(task.task_id)
      setHandledDeckTaskId(null)
      setActionFeedback({
        tone: 'success',
        message: '演示稿生成任务已加入任务中心，完成后会自动打开。',
      })
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
      icon: <Globe size={14} />,
      active: webSearchEnabled,
      onClick: () => setWebSearchEnabled(!webSearchEnabled),
      activeClass: 'bg-accent-blue/20 text-accent-blue',
    },
    {
      key: 'kb',
      label: '知识库',
      icon: <Database size={14} />,
      active: knowledgeBaseEnabled,
      onClick: () => setKnowledgeBaseEnabled(!knowledgeBaseEnabled),
      activeClass: 'bg-accent-green/20 text-accent-green',
    },
    {
      key: 'attachment',
      label: '附件',
      icon: <Paperclip size={14} />,
      active: attachmentWorkspaceOpen,
      onClick: () => currentSessionId && toggleAttachmentWorkspace(),
      disabled: !currentSessionId,
      activeClass: 'bg-accent-blue/20 text-accent-blue',
    },
    {
      key: 'memory',
      label: '记忆',
      icon: <Brain size={14} />,
      active: memoryWorkspaceOpen,
      onClick: () => currentSessionId && toggleMemoryWorkspace(),
      disabled: !currentSessionId,
      activeClass: 'bg-accent-green/20 text-accent-green',
    },
  ]

  return (
    <>
      <header
        className="sticky top-0 z-20 shrink-0 border-b border-bg-border bg-bg-primary/95 backdrop-blur-sm"
        data-testid="app-header"
      >
        {isMobile ? (
          <>
            <div className="flex items-center justify-between gap-2 px-3 py-2">
              <div className="flex min-w-0 items-center gap-2">
                <button
                  onClick={toggleSidebar}
                  className="flex h-10 w-10 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                  title="展开侧边栏"
                >
                  <PanelLeftOpen size={17} />
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
                  data-testid="header-new-chat"
                  className="flex h-10 w-10 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                  title={t('header.newChat')}
                >
                  <SquarePen size={16} />
                </button>
                <button
                  onClick={toggleTheme}
                  className="flex h-10 w-10 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                  title={`当前主题: ${themeLabel}`}
                >
                  {themeIcon}
                </button>
                <button
                  onClick={toggleLanguage}
                  data-testid="header-toggle-language-mobile"
                  className="flex h-10 min-w-10 items-center justify-center rounded-lg px-3 text-xs font-semibold text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                  title={`${t('header.language')}: ${language === 'zh-CN' ? t('settings.language.zh') : t('settings.language.en')}`}
                >
                  {t('app.language.short')}
                </button>
                <button
                  onClick={() => setMobileActionsOpen(true)}
                  className="flex h-10 w-10 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                  title="更多操作"
                >
                  <Menu size={17} />
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
                    className={`inline-flex min-h-10 shrink-0 items-center gap-1.5 rounded-full px-3 text-xs transition-colors ${
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
                  className="hidden h-10 w-10 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary md:flex"
                  title="展开侧边栏"
                >
                  <PanelLeftOpen size={17} />
                </button>
              )}
              <span className="whitespace-nowrap text-xs text-text-secondary">
                {panels.length} 个面板
              </span>
              {activePrompt && (
                <button
                  onClick={() => setSettingsOpen(true)}
                  className="hidden min-h-10 min-w-0 items-center gap-1 rounded-lg border border-bg-border px-3 text-xs text-text-secondary/70 transition-colors hover:bg-bg-hover hover:text-text-primary sm:flex"
                  title="当前角色"
                >
                  <UserCog size={13} />
                  <span className="truncate">{activePrompt.name}</span>
                  {kbStatus === 'bound' && (
                    <span title="已绑定知识库">
                      <Database size={11} className="ml-0.5 text-accent-green" />
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
                <Minus size={14} />
              </Button>
              <span className="w-4 text-center text-xs text-text-secondary">{panels.length}</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleAddPanel}
                disabled={panels.length >= 6}
                title="增加面板"
              >
                <Plus size={14} />
              </Button>
            </div>

            <div className="order-2 ml-auto flex flex-wrap items-center justify-end gap-1.5 sm:order-3 sm:ml-0">
              <AssistantPresetSelector />

              <button
                onClick={() => setWebSearchEnabled(!webSearchEnabled)}
                className={`flex min-h-10 items-center gap-1.5 rounded-lg px-3 text-xs transition-colors ${
                  webSearchEnabled
                    ? 'bg-accent-blue/20 text-accent-blue'
                    : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                }`}
                title="联网搜索"
              >
                <Globe size={14} />
                <span className="hidden sm:inline">联网</span>
              </button>

              <div className="flex items-center gap-0.5">
                <button
                  onClick={() => setKnowledgeBaseEnabled(!knowledgeBaseEnabled)}
                  className={`flex min-h-10 items-center gap-1.5 rounded-l-lg px-3 text-xs transition-colors ${
                    knowledgeBaseEnabled
                      ? 'bg-accent-green/20 text-accent-green'
                      : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                  }`}
                  title="知识库开关"
                >
                  <Database size={14} />
                  <span className="hidden sm:inline">知识库</span>
                </button>
                <button
                  onClick={() => setKbManageOpen(true)}
                  className="flex h-10 w-10 items-center justify-center rounded-r-lg border-l border-bg-border text-text-muted transition-colors hover:bg-bg-hover hover:text-text-primary"
                  title="管理知识库"
                >
                  <Settings size={13} />
                </button>
              </div>

              {showAdvancedDesktopActions && (
                <>
                  <button
                    onClick={toggleAttachmentWorkspace}
                    disabled={!currentSessionId}
                    className={`flex min-h-10 items-center gap-1.5 rounded-lg px-3 text-xs transition-colors ${
                      attachmentWorkspaceOpen
                        ? 'bg-accent-blue/20 text-accent-blue'
                        : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                    } disabled:opacity-40`}
                    title="附件工作区"
                  >
                    <Paperclip size={14} />
                    <span className="hidden sm:inline">附件</span>
                  </button>

                  <button
                    onClick={toggleMemoryWorkspace}
                    disabled={!currentSessionId}
                    className={`flex min-h-10 items-center gap-1.5 rounded-lg px-3 text-xs transition-colors ${
                      memoryWorkspaceOpen
                        ? 'bg-accent-green/20 text-accent-green'
                        : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                    } disabled:opacity-40`}
                    title="记忆工作区"
                  >
                    <Brain size={14} />
                    <span className="hidden sm:inline">记忆</span>
                  </button>

                  <HeaderMoreMenu
                    open={moreMenuOpen}
                    menuRef={moreMenuRef}
                    currentSessionId={currentSessionId}
                    sharingSession={sharingSession}
                    sessionShareCopied={sessionShareCopied}
                    generatingDeck={generatingDeck}
                    isDeckTaskActive={isDeckTaskActive}
                    resetting={resetting}
                    resetConfirm={resetConfirm}
                    onToggle={() => setMoreMenuOpen((value) => !value)}
                    onClose={() => setMoreMenuOpen(false)}
                    onShareSession={handleShareSession}
                    onGenerateReport={handleGenerateReport}
                    onOpenTaskCenter={() => setTaskCenterOpen(true)}
                    onResetSession={handleResetSession}
                  />
                </>
              )}

              <button
                onClick={handleNewChat}
                data-testid="header-new-chat"
                className="flex h-10 w-10 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                title={t('header.newChat')}
              >
                <SquarePen size={16} />
              </button>
              <button
                onClick={toggleLanguage}
                data-testid="header-toggle-language"
                className="flex h-10 min-w-10 items-center justify-center rounded-lg px-3 text-xs font-semibold text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                title={`${t('header.language')}: ${language === 'zh-CN' ? t('settings.language.zh') : t('settings.language.en')}`}
              >
                {t('app.language.short')}
              </button>
              <button
                onClick={toggleTheme}
                className="flex h-10 w-10 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                title={`当前主题: ${themeLabel}`}
              >
                {themeIcon}
              </button>
              <button
                onClick={() => setSettingsOpen(true)}
                data-testid="header-open-settings"
                className="flex h-10 w-10 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                title={t('header.settings')}
              >
                <Settings size={16} />
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

      <HeaderMobileActionsModal
        open={mobileActionsOpen}
        panelsCount={panels.length}
        currentSessionId={currentSessionId}
        sharingSession={sharingSession}
        sessionShareCopied={sessionShareCopied}
        generatingDeck={generatingDeck}
        isDeckTaskActive={isDeckTaskActive}
        resetting={resetting}
        resetConfirm={resetConfirm}
        theme={theme}
        onClose={() => setMobileActionsOpen(false)}
        onAddPanel={handleAddPanel}
        onRemovePanel={handleRemovePanel}
        onOpenTaskCenter={() => setTaskCenterOpen(true)}
        onOpenKnowledgeBase={() => setKbManageOpen(true)}
        onOpenSettings={() => setSettingsOpen(true)}
        onShareSession={handleShareSession}
        onGenerateReport={handleGenerateReport}
        onResetSession={handleResetSession}
        onNewChat={handleNewChat}
        onSetTheme={setTheme}
      />

      <DeckGenerationModal
        open={deckConfigOpen}
        onClose={() => setDeckConfigOpen(false)}
        panels={panels}
        knowledgeBaseEnabled={knowledgeBaseEnabled}
        initialTheme={currentWorkspace?.preset?.output_preset.deck_theme}
        initialSlideCount={currentWorkspace?.preset?.output_preset.target_slide_count}
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

      {deckTaskId && (
        <div className="px-3 pt-2 sm:px-4">
          <TaskProgressCard taskId={deckTaskId} taskType="generate_deck" />
        </div>
      )}

      <TaskCenterModal open={taskCenterOpen} onClose={() => setTaskCenterOpen(false)} />
      <KnowledgeBaseModal open={kbManageOpen} onClose={() => setKbManageOpen(false)} />
    </>
  )
}
