import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  ChatFile,
  ChatImage,
  ModelConfig,
  Session,
  Message,
  SourceItem,
} from '../api/client'

export interface PanelMessage {
  id: string
  role: 'user' | 'assistant' | 'error'
  content: string
  images?: ChatImage[]
  files?: ChatFile[]
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
  knowledgeBaseEnabled: boolean

  // Active system prompt id (null = use default)
  activePromptId: string | null

  // Actions – sessions
  setSessions: (sessions: Session[]) => void
  setCurrentSession: (id: string | null) => void
  addSession: (session: Session) => void
  removeSession: (id: string) => void
  updateSessionTitle: (id: string, title: string) => void
  updateSession: (
    id: string,
    patch: Partial<Pick<Session, 'title' | 'updated_at' | 'message_count'>>,
  ) => void

  // Actions – panels
  addPanel: () => void
  removePanel: (panelId: string) => void
  updatePanelModel: (panelId: string, config: Partial<ModelConfig>) => void
  setPanels: (panels: Panel[]) => void
  loadMessagesToAllPanels: (messages: Message[]) => void

  // Actions – messages
  addUserMessage: (content: string, images?: ChatImage[], files?: ChatFile[]) => string  // returns message id
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
  setKnowledgeBaseEnabled: (enabled: boolean) => void
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

function sortSessionsByUpdatedAt(sessions: Session[]): Session[] {
  return [...sessions].sort((a, b) => b.updated_at - a.updated_at)
}

function mapMessages(messages: Message[]): PanelMessage[] {
  return messages.map((message, index) => ({
    id: `loaded-${index}`,
    role: message.role,
    content: message.content,
    images: message.images,
    files: message.files,
  }))
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
      knowledgeBaseEnabled: true,
      activePromptId: null,

      setSessions: (sessions) => set({ sessions: sortSessionsByUpdatedAt(sessions) }),
      setCurrentSession: (id) => set({ currentSessionId: id }),
      addSession: (session) =>
        set((s) => ({ sessions: sortSessionsByUpdatedAt([session, ...s.sessions]) })),
      removeSession: (id) =>
        set((s) => ({ sessions: s.sessions.filter((x) => x.session_id !== id) })),
      updateSessionTitle: (id, title) =>
        set((s) => ({
          sessions: sortSessionsByUpdatedAt(s.sessions.map((x) =>
            x.session_id === id ? { ...x, title } : x,
          )),
        })),
      updateSession: (id, patch) =>
        set((s) => ({
          sessions: sortSessionsByUpdatedAt(s.sessions.map((x) =>
            x.session_id === id ? { ...x, ...patch } : x,
          )),
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
      loadMessagesToAllPanels: (messages) =>
        set((s) => ({
          panels: s.panels.map((panel) => ({
            ...panel,
            messages: mapMessages(messages),
          })),
        })),

      addUserMessage: (content, images = [], files = []) => {
        const msgId = `msg-${Date.now()}`
        set((s) => ({
          panels: s.panels.map((p) => ({
            ...p,
            messages: [
              ...p.messages,
              { id: msgId, role: 'user', content, images, files },
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
              messages: mapMessages(messages),
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
      setKnowledgeBaseEnabled: (enabled) => set({ knowledgeBaseEnabled: enabled }),
      setActivePromptId: (id) => set({ activePromptId: id }),
    }),
    {
      name: 'ai-kb-chat-store',
      partialize: (s) => ({
        sidebarOpen: s.sidebarOpen,
        webSearchEnabled: s.webSearchEnabled,
        knowledgeBaseEnabled: s.knowledgeBaseEnabled,
        activePromptId: s.activePromptId,
        panels: s.panels.map((p) => ({ ...p, messages: [] })),
      }),
    },
  ),
)
