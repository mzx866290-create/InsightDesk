import React, { useEffect, useRef, useState } from 'react'
import {
  PanelLeftOpen,
  Plus,
  Minus,
  Menu,
  Monitor,
  Settings,
  SquarePen,
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
import { DeckEditorModal } from '../reports/DeckEditorModal'
import { DeckGenerationModal } from '../reports/DeckGenerationModal'
import { TaskProgressCard } from '../cards/TaskProgressCard'
import { TaskCenterModal } from '../tasks/TaskCenterModal'
import { KnowledgeBaseModal } from '../settings/KnowledgeBaseModal'
import { AssistantPresetSelector } from '../chat/AssistantPresetSelector'
import { HeaderMobileActionsModal } from './header/HeaderMobileActionsModal'
import { HeaderMoreMenu } from './header/HeaderMoreMenu'
import type { HeaderActionFeedback } from './header/headerTypes'
import { useHeaderActivePrompt } from './header/useHeaderActivePrompt'
import { useHeaderDeckActions } from './header/useHeaderDeckActions'
import { useHeaderSessionActions } from './header/useHeaderSessionActions'
import { useHeaderViewport } from './header/useHeaderViewport'

export const Header: React.FC = () => {
  const {
    sidebarOpen,
    toggleSidebar,
    workspaces,
    panels,
    addPanel,
    removePanel,
    knowledgeBaseEnabled,
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
  const { t } = useI18n()
  const activePrompt = useHeaderActivePrompt(activePromptId)
  const [taskCenterOpen, setTaskCenterOpen] = useState(false)
  const [kbManageOpen, setKbManageOpen] = useState(false)
  const [actionFeedback, setActionFeedback] = useState<HeaderActionFeedback | null>(null)
  const [moreMenuOpen, setMoreMenuOpen] = useState(false)
  const moreMenuRef = useRef<HTMLDivElement>(null)
  const isMobile = useHeaderViewport()
  const [mobileActionsOpen, setMobileActionsOpen] = useState(false)
  const hasAnyMessages = panels.some((panel) => panel.messages.length > 0)
  const showAdvancedDesktopActions = hasAnyMessages
  const {
    deckTaskId,
    deckConfigOpen,
    setDeckConfigOpen,
    deckOpen,
    setDeckOpen,
    deckData,
    setDeckData,
    generatingDeck,
    isDeckTaskActive,
    handleGenerateReport,
    handleGenerateDeck,
  } = useHeaderDeckActions({
    currentSessionId,
    knowledgeBaseEnabled,
    setActionFeedback,
  })
  const {
    resetting,
    resetConfirm,
    sharingSession,
    sessionShareCopied,
    handleNewChat,
    handleResetSession,
    handleShareSession,
  } = useHeaderSessionActions({
    currentSessionId,
    currentWorkspaceId,
    addSession,
    adjustWorkspaceSessionCount,
    setCurrentSession,
    clearMessages,
    updateSession,
    setActionFeedback,
  })

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

  const handleAddPanel = () => {
    setWelcomeGuideDismissed(true)
    addPanel()
  }

  const handleRemovePanel = () => {
    if (panels.length <= 1) return
    removePanel(panels[panels.length - 1].id)
  }

  const themeLabel =
    theme === 'dark' ? '深色' : theme === 'light' ? '浅色' : '跟随系统'
  const themeIcon =
    theme === 'dark' ? <Sun size={15} /> : theme === 'light' ? <Moon size={15} /> : <Monitor size={15} />
  const mobileWorkspaceActions = [
    {
      key: 'attachment',
      label: '附件区',
      icon: <Paperclip size={14} />,
      active: attachmentWorkspaceOpen,
      onClick: () => currentSessionId && toggleAttachmentWorkspace(),
      disabled: !currentSessionId,
      activeClass: 'bg-accent-blue/20 text-accent-blue',
    },
    {
      key: 'memory',
      label: '记忆区',
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
                  onClick={() => setMobileActionsOpen(true)}
                  className="flex h-10 w-10 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                  title="更多操作"
                >
                  <Menu size={17} />
                </button>
              </div>
            </div>

            {showAdvancedDesktopActions && currentSessionId && (
              <div className="overflow-x-auto px-3 pb-2">
                <div className="flex gap-2">
                  {mobileWorkspaceActions.map((action) => (
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
            )}
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
              <button
                onClick={handleNewChat}
                data-testid="header-new-chat"
                className="flex h-10 min-w-10 items-center justify-center gap-1.5 rounded-lg px-2 text-xs text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                title={t('header.newChat')}
              >
                <SquarePen size={15} />
                <span className="hidden xl:inline">{t('header.newChat')}</span>
              </button>

              <AssistantPresetSelector />

              <button
                onClick={() => setKbManageOpen(true)}
                data-testid="header-open-kb"
                className="flex min-h-10 items-center gap-1.5 rounded-lg px-3 text-xs text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                title="知识库管理"
              >
                <Database size={14} />
                <span className="hidden xl:inline">知识库管理</span>
              </button>

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
