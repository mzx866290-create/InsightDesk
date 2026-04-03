import React, { useEffect, useState } from 'react'
import {
  PanelLeftOpen,
  Plus,
  Minus,
  Globe,
  Settings,
  SquarePen,
  UserCog,
  FileText,
  RotateCcw,
  Database,
} from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import { Button } from '../ui/Button'
import { createDeckDraft, createSession, getSystemPrompts, resetSession } from '../../api/client'
import { DeckEditorModal } from '../reports/DeckEditorModal'
import { DeckGenerationModal } from '../reports/DeckGenerationModal'
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
    setSettingsOpen,
    activePromptId,
    currentSessionId,
  } = useChatStore()

  const [activePrompt, setActivePrompt] = useState<SystemPrompt | null>(null)
  const [deckConfigOpen, setDeckConfigOpen] = useState(false)
  const [deckOpen, setDeckOpen] = useState(false)
  const [deckData, setDeckData] = useState<DeckSpec | null>(null)
  const [generatingDeck, setGeneratingDeck] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [resetConfirm, setResetConfirm] = useState(false)

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
    } catch {
      // sidebar will show error
    }
  }

  const handleGenerateReport = async () => {
    if (!currentSessionId || generatingDeck) return
    setDeckConfigOpen(true)
  }

  const handleGenerateDeck = async (payload: {
    panel_config: (typeof panels)[number]['modelConfig']
    target_slide_count: number
  }) => {
    if (!currentSessionId) return
    setGeneratingDeck(true)
    try {
      const data = await createDeckDraft({
        session_id: currentSessionId,
        panel_config: payload.panel_config,
        knowledge_base_enabled: knowledgeBaseEnabled,
        target_slide_count: payload.target_slide_count,
      })
      setDeckData(data)
      setDeckOpen(true)
    } catch (e) {
      alert('Failed to generate deck: ' + (e as Error).message)
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
    } catch (e) {
      alert('Reset failed: ' + (e as Error).message)
    } finally {
      setResetting(false)
    }
  }

  const kbStatus = activePrompt?.vector_store_id ? 'bound' : 'default'

  return (
    <>
      <header className="sticky top-0 z-20 shrink-0 border-b border-bg-border bg-bg-primary/95 backdrop-blur-sm">
        <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 sm:px-4">
          <div className="flex min-w-0 items-center gap-2">
            <button
              onClick={toggleSidebar}
              className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary md:hidden"
              title="Open sidebar"
            >
              <PanelLeftOpen size={16} />
            </button>
            {!sidebarOpen && (
              <button
                onClick={toggleSidebar}
                className="hidden rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary md:flex"
                title="Open sidebar"
              >
                <PanelLeftOpen size={16} />
              </button>
            )}
            <span className="whitespace-nowrap text-xs text-text-secondary">
              {panels.length} panels
            </span>
            {activePrompt && (
              <button
                onClick={() => setSettingsOpen(true)}
                className="hidden min-w-0 items-center gap-1 rounded-lg border border-bg-border px-2 py-1 text-[10px] text-text-secondary/70 transition-colors hover:bg-bg-hover hover:text-text-primary sm:flex"
                title="Current prompt"
              >
                <UserCog size={11} />
                <span className="truncate">{activePrompt.name}</span>
                {kbStatus === 'bound' && (
                  <span title="Knowledge base bound">
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
              onClick={() => panels.length > 1 && removePanel(panels[panels.length - 1].id)}
              disabled={panels.length <= 1}
              title="Remove panel"
            >
              <Minus size={13} />
            </Button>
            <span className="w-4 text-center text-xs text-text-secondary">{panels.length}</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={addPanel}
              disabled={panels.length >= 6}
              title="Add panel"
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
              title="Web search"
            >
              <Globe size={13} />
              <span className="hidden sm:inline">Web</span>
            </button>

            <button
              onClick={() => setKnowledgeBaseEnabled(!knowledgeBaseEnabled)}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs transition-colors ${
                knowledgeBaseEnabled
                  ? 'bg-accent-green/20 text-accent-green'
                  : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
              }`}
              title="Knowledge base"
            >
              <Database size={13} />
              <span className="hidden sm:inline">KB</span>
            </button>

            <button
              onClick={handleResetSession}
              disabled={resetting || !currentSessionId}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs transition-colors ${
                resetConfirm
                  ? 'border border-accent-red/40 bg-accent-red/20 text-accent-red'
                  : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
              } disabled:opacity-40`}
              title={resetConfirm ? 'Click again to confirm reset' : 'Reset session'}
            >
              {resetting ? (
                <span className="h-3 w-3 rounded-full border border-current border-t-transparent animate-spin" />
              ) : (
                <RotateCcw size={13} />
              )}
              <span className="hidden sm:inline">{resetConfirm ? 'Confirm reset?' : 'Reset'}</span>
            </button>

            <button
              onClick={handleGenerateReport}
              disabled={generatingDeck || !currentSessionId}
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary disabled:opacity-40"
              title="Generate deck"
            >
              {generatingDeck ? (
                <span className="h-3 w-3 rounded-full border border-current border-t-transparent animate-spin" />
              ) : (
                <FileText size={13} />
              )}
              <span className="hidden sm:inline">Deck</span>
            </button>

            <button
              onClick={handleNewChat}
              className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
              title="New chat"
            >
              <SquarePen size={15} />
            </button>
            <button
              onClick={() => setSettingsOpen(true)}
              className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
              title="Settings"
            >
              <Settings size={15} />
            </button>
          </div>
        </div>
      </header>

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
          onDeckChange={setDeckData}
        />
      )}
    </>
  )
}
