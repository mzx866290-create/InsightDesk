import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { ModelConfig, Session, Message, SourceItem } from '../api/client'

export interface PanelMessage {
  id: string
  role: 'user' | 'assistant' | 'error'
  content: string
  streaming?: boolean
  sources?: SourceItem[]
  errorCode?: string
  suggestion?: string
  taskId?: string
  taskType?: string
}

export interface Panel {
  id: string
  modelConfig: ModelConfig
  messages: PanelMessage[]
}

interface ChatState {
  // Sessions
  sessions: Session[]
  currentSessionId: string | null

  // Panels (multi-model)
  panels: Panel[]

  // UI state
  sidebarOpen: boolean
  settingsOpen: boolean
  webSearchEnabled: boolean

  // Active system prompt id (null = use default)
  activePromptId: string | null

  // Actions – sessions
  setSessions: (sessions: Session[]) => void
  setCurrentSession: (id: string | null) => void
  addSession: (session: Session) => void
  removeSession: (id: string) => void
  updateSessionTitle: (id: string, title: string) => void

  // Actions – panels
  addPanel: () => void
  removePanel: (panelId: string) => void
  updatePanelModel: (panelId: string, config: Partial<ModelConfig>) => void
  setPanels: (panels: Panel[]) => void

  // Actions – messages
  addUserMessage: (content: string) => string  // returns message id
  appendChunk: (panelId: string, msgId: string, chunk: string) => void
  setAssistantMessage: (panelId: string, msgId: string, content: string, streaming: boolean) => void
  setSources: (panelId: string, msgId: string, sources: SourceItem[]) => void
  addErrorMessage: (panelId: string, content: string, errorCode?: string, suggestion?: string) => void
  setTaskId: (panelId: string, msgId: string, taskId: string, taskType?: string) => void
  loadMessages: (panelId: string, messages: Message[]) => void
  clearMessages: () => void

  // Actions – UI
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  setSettingsOpen: (open: boolean) => void
  setWebSearchEnabled: (enabled: boolean) => void
  setActivePromptId: (id: string | null) => void
}

function defaultModelConfig(panelId: string): ModelConfig {
  return {
    panel_id: panelId,
    provider: 'local',
    model: 'qwen2.5:7b',
    base_url: 'http://localhost:11434',
    api_key: '',
    temperature: 0.3,
    agent_mode: 'auto',
  }
}

function newPanel(): Panel {
  const id = `panel-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
  return { id, modelConfig: defaultModelConfig(id), messages: [] }
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, _get) => ({
      sessions: [],
      currentSessionId: null,
      panels: [newPanel()],
      sidebarOpen: true,
      settingsOpen: false,
      webSearchEnabled: false,
      activePromptId: null,

      setSessions: (sessions) => set({ sessions }),
      setCurrentSession: (id) => set({ currentSessionId: id }),
      addSession: (session) =>
        set((s) => ({ sessions: [session, ...s.sessions] })),
      removeSession: (id) =>
        set((s) => ({ sessions: s.sessions.filter((x) => x.session_id !== id) })),
      updateSessionTitle: (id, title) =>
        set((s) => ({
          sessions: s.sessions.map((x) =>
            x.session_id === id ? { ...x, title } : x,
          ),
        })),

      addPanel: () =>
        set((s) => {
          if (s.panels.length >= 6) return s
          return { panels: [...s.panels, newPanel()] }
        }),
      removePanel: (panelId) =>
        set((s) => {
          if (s.panels.length <= 1) return s
          return { panels: s.panels.filter((p) => p.id !== panelId) }
        }),
      updatePanelModel: (panelId, config) =>
        set((s) => ({
          panels: s.panels.map((p) =>
            p.id === panelId
              ? { ...p, modelConfig: { ...p.modelConfig, ...config, panel_id: panelId } }
              : p,
          ),
        })),
      setPanels: (panels) => set({ panels }),

      addUserMessage: (content) => {
        const msgId = `msg-${Date.now()}`
        set((s) => ({
          panels: s.panels.map((p) => ({
            ...p,
            messages: [
              ...p.messages,
              { id: msgId, role: 'user', content },
            ],
          })),
        }))
        return msgId
      },

      appendChunk: (panelId, msgId, chunk) =>
        set((s) => ({
          panels: s.panels.map((p) => {
            if (p.id !== panelId) return p
            const existing = p.messages.find((m) => m.id === msgId)
            if (existing) {
              return {
                ...p,
                messages: p.messages.map((m) =>
                  m.id === msgId
                    ? { ...m, content: m.content + chunk, streaming: true }
                    : m,
                ),
              }
            }
            // Create new assistant message
            return {
              ...p,
              messages: [
                ...p.messages,
                { id: msgId, role: 'assistant' as const, content: chunk, streaming: true },
              ],
            }
          }),
        })),

      setAssistantMessage: (panelId, msgId, content, streaming) =>
        set((s) => ({
          panels: s.panels.map((p) => {
            if (p.id !== panelId) return p
            return {
              ...p,
              messages: p.messages.map((m) =>
                m.id === msgId ? { ...m, content, streaming } : m,
              ),
            }
          }),
        })),

      setSources: (panelId, msgId, sources) =>
        set((s) => ({
          panels: s.panels.map((p) => {
            if (p.id !== panelId) return p
            return {
              ...p,
              messages: p.messages.map((m) =>
                m.id === msgId ? { ...m, sources } : m,
              ),
            }
          }),
        })),

      addErrorMessage: (panelId, content, errorCode, suggestion) =>
        set((s) => ({
          panels: s.panels.map((p) => {
            if (p.id !== panelId) return p
            const msgId = `error-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
            return {
              ...p,
              messages: [
                ...p.messages,
                { id: msgId, role: 'error' as const, content, errorCode, suggestion },
              ],
            }
          }),
        })),

      setTaskId: (panelId, msgId, taskId, taskType) =>
        set((s) => ({
          panels: s.panels.map((p) => {
            if (p.id !== panelId) return p
            return {
              ...p,
              messages: p.messages.map((m) =>
                m.id === msgId ? { ...m, taskId, taskType } : m,
              ),
            }
          }),
        })),

      loadMessages: (panelId, messages) =>
        set((s) => ({
          panels: s.panels.map((p) => {
            if (p.id !== panelId) return p
            return {
              ...p,
              messages: messages.map((m, i) => ({
                id: `loaded-${i}`,
                role: m.role,
                content: m.content,
              })),
            }
          }),
        })),

      clearMessages: () =>
        set((s) => ({
          panels: s.panels.map((p) => ({ ...p, messages: [] })),
        })),

      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      setSettingsOpen: (open) => set({ settingsOpen: open }),
      setWebSearchEnabled: (enabled) => set({ webSearchEnabled: enabled }),
      setActivePromptId: (id) => set({ activePromptId: id }),
    }),
    {
      name: 'ai-kb-chat-store',
      partialize: (s) => ({
        sidebarOpen: s.sidebarOpen,
        webSearchEnabled: s.webSearchEnabled,
        activePromptId: s.activePromptId,
        panels: s.panels.map((p) => ({ ...p, messages: [] })),
      }),
    },
  ),
)
