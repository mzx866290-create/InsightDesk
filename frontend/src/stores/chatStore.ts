import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  Bookmark,
  ChatFile,
  ChatImage,
  ModelConfig,
  MessageFeedbackValue,
  Session,
  Workspace,
  Message,
  SourceItem,
} from '../api/client'
import { normalizeModelConfig } from '../api/client'
import type { WorkflowNode } from './workflowStore'

export type ErrorRetryMode = 'rerun' | 'continue'

export interface PanelMessage {
  id: string
  serverMessageId?: number
  role: 'user' | 'assistant' | 'error'
  content: string
  images?: ChatImage[]
  files?: ChatFile[]
  modelId?: string
  panelId?: string
  answerGroupId?: string
  streaming?: boolean
  sources?: SourceItem[]
  errorCode?: string
  suggestion?: string
  taskId?: string
  taskType?: string
  workflowNodes?: WorkflowNode[]
  timestamp?: number
  feedbackValue?: MessageFeedbackValue
  retryMode?: ErrorRetryMode
}

export type ThemeMode = 'dark' | 'light' | 'system'
export type BookmarkedMessage = Bookmark

export interface Panel {
  id: string
  modelConfig: ModelConfig
  messages: PanelMessage[]
}

export interface ModelPreset {
  id: string
  name: string
  modelConfig: ModelConfig
  createdAt: number
  updatedAt: number
}

export interface CloudModelProfile {
  id: string
  name: string
  modelConfig: ModelConfig
  createdAt: number
  updatedAt: number
}

interface ComposerSeed {
  token: number
  text: string
  images: ChatImage[]
  files: ChatFile[]
  editAnswerGroupId: string | null
}

export interface JumpTarget {
  sessionId: string
  role: 'user' | 'assistant'
  panelId?: string
  answerGroupId?: string
  messageId?: number
}

interface ChatState {
  workspaces: Workspace[]
  currentWorkspaceId: string | null

  // Sessions
  sessions: Session[]
  currentSessionId: string | null

  // Panels (multi-model)
  panels: Panel[]
  modelPresets: ModelPreset[]
  cloudModelProfiles: CloudModelProfile[]

  // UI state
  sidebarOpen: boolean
  settingsOpen: boolean
  webSearchEnabled: boolean
  knowledgeBaseEnabled: boolean
  enabledMcpServers: string[]
  attachmentWorkspaceOpen: boolean
  memoryWorkspaceOpen: boolean
  welcomeGuideDismissed: boolean
  composerSeed: ComposerSeed
  jumpTarget: JumpTarget | null

  // Active system prompt id (null = use default)
  activePromptId: string | null

  // 主题
  theme: ThemeMode

  // 书签消息
  bookmarks: BookmarkedMessage[]

  // Actions – sessions
  setWorkspaces: (workspaces: Workspace[]) => void
  setCurrentWorkspace: (id: string | null) => void
  addWorkspace: (workspace: Workspace) => void
  updateWorkspace: (workspaceId: string, patch: Partial<Workspace>) => void
  adjustWorkspaceSessionCount: (workspaceId: string, delta: number) => void
  setSessions: (sessions: Session[]) => void
  setCurrentSession: (id: string | null) => void
  addSession: (session: Session) => void
  removeSession: (id: string) => void
  updateSessionTitle: (id: string, title: string) => void
  updateSession: (id: string, patch: Partial<Session>) => void

  // Actions – panels
  addPanel: () => void
  removePanel: (panelId: string) => void
  updatePanelModel: (panelId: string, config: Partial<ModelConfig>) => void
  saveModelPreset: (name: string, modelConfig: ModelConfig) => void
  deleteModelPreset: (presetId: string) => void
  applyModelPreset: (panelId: string, presetId: string) => void
  saveCloudModelProfile: (profile: {
    id?: string
    name: string
    modelConfig: ModelConfig
  }) => void
  deleteCloudModelProfile: (profileId: string) => void
  applyCloudModelProfile: (panelId: string, profileId: string) => void
  setPanels: (panels: Panel[]) => void
  loadMessagesToAllPanels: (messages: Message[]) => void

  // Actions – messages
  addUserMessage: (content: string, images?: ChatImage[], files?: ChatFile[], answerGroupId?: string) => string  // returns message id
  appendChunk: (
    panelId: string,
    msgId: string,
    chunk: string,
    meta?: Partial<Pick<PanelMessage, 'modelId' | 'answerGroupId'>>,
  ) => void
  setAssistantMessage: (panelId: string, msgId: string, content: string, streaming: boolean) => void
  setAssistantStreaming: (panelId: string, msgId: string, streaming: boolean) => void
  setSources: (
    panelId: string,
    msgId: string,
    sources: SourceItem[],
    meta?: Partial<Pick<PanelMessage, 'modelId' | 'answerGroupId'>>,
  ) => void
  addErrorMessage: (
    panelId: string,
    content: string,
    errorCode?: string,
    suggestion?: string,
    meta?: Partial<Pick<PanelMessage, 'answerGroupId' | 'retryMode'>>,
  ) => void
  setTaskId: (panelId: string, msgId: string, taskId: string, taskType?: string) => void
  loadMessages: (panelId: string, messages: Message[]) => void
  updateMessage: (panelId: string, msgId: string, patch: Partial<PanelMessage>) => void
  removeMessage: (panelId: string, msgId: string) => void
  truncateMessagesFromAnswerGroup: (
    answerGroupId: string,
    userPatch?: Partial<Pick<PanelMessage, 'content' | 'images' | 'files' | 'timestamp'>>,
  ) => void
  replaceAssistantMessageByAnswerGroup: (
    panelId: string,
    answerGroupId: string,
    patch: Partial<Pick<PanelMessage, 'content' | 'sources' | 'modelId' | 'streaming' | 'taskId' | 'taskType' | 'workflowNodes' | 'serverMessageId' | 'timestamp' | 'feedbackValue' | 'panelId'>>,
  ) => void
  clearMessages: () => void

  // Actions – UI
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  setSettingsOpen: (open: boolean) => void
  setWebSearchEnabled: (enabled: boolean) => void
  setKnowledgeBaseEnabled: (enabled: boolean) => void
  setEnabledMcpServers: (servers: string[]) => void
  toggleAttachmentWorkspace: () => void
  setAttachmentWorkspaceOpen: (open: boolean) => void
  toggleMemoryWorkspace: () => void
  setMemoryWorkspaceOpen: (open: boolean) => void
  setWelcomeGuideDismissed: (dismissed: boolean) => void
  setJumpTarget: (target: JumpTarget | null) => void
  clearJumpTarget: () => void
  pushComposerSeed: (seed: {
    text?: string
    images?: ChatImage[]
    files?: ChatFile[]
    editAnswerGroupId?: string | null
  }) => void
  setActivePromptId: (id: string | null) => void
  setTheme: (theme: ThemeMode) => void
  toggleTheme: () => void
  setBookmarks: (bookmarks: BookmarkedMessage[]) => void
  addBookmark: (msg: BookmarkedMessage) => void
  removeBookmark: (id: string) => void
  isBookmarked: (id: string) => boolean
}

function defaultModelConfig(panelId: string): ModelConfig {
  return normalizeModelConfig({
    panel_id: panelId,
    connection_type: 'ollama',
    provider: 'ollama',
    model: 'qwen3.5-2B:latest',
    base_url: 'http://localhost:11434',
    api_key: '',
    temperature: 0.3,
    agent_mode: 'auto',
  })
}

function newPanel(): Panel {
  const id = `panel-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
  return { id, modelConfig: defaultModelConfig(id), messages: [] }
}

function sortSessionsByUpdatedAt(sessions: Session[]): Session[] {
  return [...sessions].sort((a, b) => {
    if ((a.is_pinned ?? false) !== (b.is_pinned ?? false)) {
      return a.is_pinned ? -1 : 1
    }

    const aOrder = Number(a.session_order ?? 0)
    const bOrder = Number(b.session_order ?? 0)
    const aRanked = aOrder > 0
    const bRanked = bOrder > 0
    if (aRanked !== bRanked) {
      return aRanked ? -1 : 1
    }
    if (aRanked && bRanked && aOrder !== bOrder) {
      return bOrder - aOrder
    }

    return b.updated_at - a.updated_at
  })
}

function sortWorkspaces(workspaces: Workspace[]): Workspace[] {
  return [...workspaces].sort((a, b) => {
    if (a.is_active !== b.is_active) return a.is_active ? -1 : 1
    return b.updated_at - a.updated_at
  })
}

function mapMessages(messages: Message[]): PanelMessage[] {
  return messages.map((message, index) => ({
    id: typeof message.id === 'number' ? `db-${message.id}` : `loaded-${index}`,
    serverMessageId: message.id,
    role: message.role,
    content: message.content,
    images: message.images,
    files: message.files,
    sources: message.sources,
    modelId: message.model_id,
    panelId: message.panel_id,
    answerGroupId: message.answer_group_id,
    taskId: message.task_id,
    taskType: message.task_type,
    workflowNodes: message.workflow_nodes,
    timestamp: message.timestamp,
    feedbackValue: message.feedback_value,
  }))
}

function normalizeBookmarkMessage(bookmark: BookmarkedMessage): BookmarkedMessage {
  const rawCreatedAt =
    typeof bookmark.createdAt === 'number' && Number.isFinite(bookmark.createdAt)
      ? bookmark.createdAt
      : Date.now() / 1000
  const rawUpdatedAt =
    typeof bookmark.updatedAt === 'number' && Number.isFinite(bookmark.updatedAt)
      ? bookmark.updatedAt
      : rawCreatedAt
  const createdAt =
    rawCreatedAt > 1e12 ? rawCreatedAt / 1000 : rawCreatedAt
  const updatedAt =
    rawUpdatedAt > 1e12 ? rawUpdatedAt / 1000 : rawUpdatedAt

  return {
    ...bookmark,
    sessionId: bookmark.sessionId ?? '',
    sessionTitle: bookmark.sessionTitle ?? '',
    panelId: bookmark.panelId ?? '',
    answerGroupId: bookmark.answerGroupId ?? '',
    content: bookmark.content ?? '',
    createdAt,
    updatedAt,
    source: bookmark.source === 'local' ? 'local' : 'remote',
  }
}

function sameBookmarkTarget(a: BookmarkedMessage, b: BookmarkedMessage): boolean {
  if (typeof a.messageId === 'number' && typeof b.messageId === 'number') {
    return a.messageId === b.messageId
  }

  if (
    a.sessionId &&
    b.sessionId &&
    a.sessionId === b.sessionId &&
    a.role === b.role &&
    (a.answerGroupId ?? '') &&
    a.answerGroupId === b.answerGroupId
  ) {
    return a.role === 'user' || (a.panelId ?? '') === (b.panelId ?? '')
  }

  return a.source === 'local' && b.source === 'local' && a.id === b.id
}

function sortBookmarks(bookmarks: BookmarkedMessage[]): BookmarkedMessage[] {
  return [...bookmarks].sort((a, b) => {
    const aTs = a.updatedAt ?? a.createdAt
    const bTs = b.updatedAt ?? b.createdAt
    return bTs - aTs
  })
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, _get) => ({
      workspaces: [],
      currentWorkspaceId: null,
      sessions: [],
      currentSessionId: null,
      panels: [newPanel()],
      modelPresets: [],
      cloudModelProfiles: [],
      sidebarOpen: true,
      settingsOpen: false,
      webSearchEnabled: false,
      knowledgeBaseEnabled: true,
      enabledMcpServers: ['knowledge-base', 'web-search'],
      attachmentWorkspaceOpen: false,
      memoryWorkspaceOpen: false,
      welcomeGuideDismissed: false,
      jumpTarget: null,
      composerSeed: {
        token: 0,
        text: '',
        images: [],
        files: [],
        editAnswerGroupId: null,
      },
      activePromptId: null,
      theme: 'system',
      bookmarks: [],

      setWorkspaces: (workspaces) => set({ workspaces: sortWorkspaces(workspaces) }),
      setCurrentWorkspace: (id) => set({ currentWorkspaceId: id }),
      addWorkspace: (workspace) =>
        set((s) => ({
          workspaces: sortWorkspaces([
            workspace,
            ...s.workspaces.filter((item) => item.workspace_id !== workspace.workspace_id),
          ]),
        })),
      updateWorkspace: (workspaceId, patch) =>
        set((s) => ({
          workspaces: sortWorkspaces(
            s.workspaces.map((workspace) =>
              workspace.workspace_id === workspaceId ? { ...workspace, ...patch } : workspace,
            ),
          ),
        })),
      adjustWorkspaceSessionCount: (workspaceId, delta) =>
        set((s) => ({
          workspaces: sortWorkspaces(
            s.workspaces.map((workspace) =>
              workspace.workspace_id === workspaceId
                ? {
                    ...workspace,
                    session_count: Math.max(0, workspace.session_count + delta),
                  }
                : workspace,
            ),
          ),
        })),
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
              ? {
                  ...p,
                  modelConfig: normalizeModelConfig({
                    ...p.modelConfig,
                    ...config,
                    panel_id: panelId,
                  }),
                }
              : p,
          ),
        })),
      saveModelPreset: (name, modelConfig) =>
        set((s) => {
          const trimmedName = name.trim()
          if (!trimmedName) return s
          const now = Date.now()
          const existingPreset = s.modelPresets.find(
            (preset) => preset.name.toLowerCase() === trimmedName.toLowerCase(),
          )
          const normalizedModelConfig = normalizeModelConfig({
            ...modelConfig,
            panel_id: modelConfig.panel_id || `preset-${now}`,
          })

          if (existingPreset) {
            return {
              modelPresets: s.modelPresets.map((preset) =>
                preset.id === existingPreset.id
                  ? {
                      ...preset,
                      name: trimmedName,
                      modelConfig: normalizedModelConfig,
                      updatedAt: now,
                    }
                  : preset,
              ),
            }
          }

          const presetId = `preset-${now}-${Math.random().toString(36).slice(2, 7)}`
          return {
            modelPresets: [
              {
                id: presetId,
                name: trimmedName,
                modelConfig: normalizedModelConfig,
                createdAt: now,
                updatedAt: now,
              },
              ...s.modelPresets,
            ],
          }
        }),
      deleteModelPreset: (presetId) =>
        set((s) => ({
          modelPresets: s.modelPresets.filter((preset) => preset.id !== presetId),
        })),
      applyModelPreset: (panelId, presetId) =>
        set((s) => {
          const preset = s.modelPresets.find((item) => item.id === presetId)
          if (!preset) return s

          return {
            panels: s.panels.map((panel) =>
              panel.id === panelId
                ? {
                    ...panel,
                    modelConfig: normalizeModelConfig({
                      ...preset.modelConfig,
                      panel_id: panelId,
                    }),
                  }
                : panel,
            ),
          }
        }),
      saveCloudModelProfile: ({ id, name, modelConfig }) =>
        set((s) => {
          const trimmedName = name.trim()
          if (!trimmedName) return s

          const normalizedModelConfig = normalizeModelConfig({
            ...modelConfig,
            panel_id: modelConfig.panel_id || `cloud-profile-${Date.now()}`,
            connection_type: 'openai_compatible',
            provider: 'openai_compatible',
          })
          const now = Date.now()
          const existingProfile = id
            ? s.cloudModelProfiles.find((profile) => profile.id === id)
            : s.cloudModelProfiles.find(
                (profile) => profile.name.toLowerCase() === trimmedName.toLowerCase(),
              )

          if (existingProfile) {
            return {
              cloudModelProfiles: s.cloudModelProfiles.map((profile) =>
                profile.id === existingProfile.id
                  ? {
                      ...profile,
                      name: trimmedName,
                      modelConfig: normalizedModelConfig,
                      updatedAt: now,
                    }
                  : profile,
              ),
            }
          }

          const profileId = `cloud-profile-${now}-${Math.random().toString(36).slice(2, 7)}`
          return {
            cloudModelProfiles: [
              {
                id: profileId,
                name: trimmedName,
                modelConfig: normalizedModelConfig,
                createdAt: now,
                updatedAt: now,
              },
              ...s.cloudModelProfiles,
            ],
          }
        }),
      deleteCloudModelProfile: (profileId) =>
        set((s) => ({
          cloudModelProfiles: s.cloudModelProfiles.filter((profile) => profile.id !== profileId),
        })),
      applyCloudModelProfile: (panelId, profileId) =>
        set((s) => {
          const profile = s.cloudModelProfiles.find((item) => item.id === profileId)
          if (!profile) return s

          return {
            panels: s.panels.map((panel) =>
              panel.id === panelId
                ? {
                    ...panel,
                    modelConfig: normalizeModelConfig({
                      ...profile.modelConfig,
                      panel_id: panelId,
                      connection_type: 'openai_compatible',
                      provider: 'openai_compatible',
                    }),
                  }
                : panel,
            ),
          }
        }),
      setPanels: (panels) =>
        set({
          panels: panels.map((panel) => ({
            ...panel,
            modelConfig: normalizeModelConfig({
              ...panel.modelConfig,
              panel_id: panel.id,
            }),
          })),
        }),
      loadMessagesToAllPanels: (messages) =>
        set((s) => ({
          panels: s.panels.map((panel) => ({
            ...panel,
            messages: mapMessages(messages),
          })),
        })),

      addUserMessage: (content, images = [], files = [], answerGroupId) => {
        const msgId = `msg-${Date.now()}`
        const now = Date.now() / 1000
        set((s) => ({
          panels: s.panels.map((p) => ({
            ...p,
            messages: [
              ...p.messages,
              {
                id: msgId,
                role: 'user',
                content,
                images,
                files,
                answerGroupId,
                timestamp: now,
              },
            ],
          })),
        }))
        return msgId
      },

      appendChunk: (panelId, msgId, chunk, meta = {}) =>
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
                {
                  id: msgId,
                  role: 'assistant' as const,
                  content: chunk,
                  streaming: true,
                  modelId: meta.modelId,
                  panelId,
                  answerGroupId: meta.answerGroupId,
                  timestamp: Date.now() / 1000,
                  feedbackValue: 0,
                },
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

      setSources: (panelId, msgId, sources, meta = {}) =>
        set((s) => ({
          panels: s.panels.map((p) => {
            if (p.id !== panelId) return p
            const existing = p.messages.find((m) => m.id === msgId)
            if (!existing) {
              return {
                ...p,
                messages: [
                  ...p.messages,
                  {
                    id: msgId,
                    role: 'assistant' as const,
                    content: '',
                    streaming: true,
                    sources,
                    modelId: meta.modelId,
                    panelId,
                    answerGroupId: meta.answerGroupId,
                    timestamp: Date.now() / 1000,
                    feedbackValue: 0,
                  },
                ],
              }
            }
            return {
              ...p,
              messages: p.messages.map((m) =>
                m.id === msgId ? { ...m, sources } : m,
              ),
            }
          }),
        })),

      addErrorMessage: (panelId, content, errorCode, suggestion, meta) =>
        set((s) => ({
          panels: s.panels.map((p) => {
            if (p.id !== panelId) return p
            const msgId = `error-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
            return {
              ...p,
              messages: [
                ...p.messages,
                {
                  id: msgId,
                  role: 'error' as const,
                  content,
                  errorCode,
                  suggestion,
                  panelId,
                  answerGroupId: meta?.answerGroupId,
                  retryMode: meta?.retryMode,
                  timestamp: Date.now() / 1000,
                },
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

      updateMessage: (panelId, msgId, patch) =>
        set((s) => ({
          panels: s.panels.map((p) => {
            if (p.id !== panelId) return p
            return {
              ...p,
              messages: p.messages.map((m) =>
                m.id === msgId ? { ...m, ...patch } : m,
              ),
            }
          }),
        })),

      removeMessage: (panelId, msgId) =>
        set((s) => ({
          panels: s.panels.map((p) => {
            if (p.id !== panelId) return p
            return {
              ...p,
              messages: p.messages.filter((m) => m.id !== msgId),
            }
          }),
        })),

      truncateMessagesFromAnswerGroup: (answerGroupId, userPatch = {}) =>
        set((s) => ({
          panels: s.panels.map((panel) => {
            const userMessageIndex = panel.messages.findIndex(
              (message) =>
                message.role === 'user' && message.answerGroupId === answerGroupId,
            )
            if (userMessageIndex < 0) return panel

            const nextMessages = panel.messages
              .slice(0, userMessageIndex + 1)
              .map((message, index) => {
                if (index !== userMessageIndex) return message
                return {
                  ...message,
                  ...userPatch,
                }
              })

            return {
              ...panel,
              messages: nextMessages,
            }
          }),
        })),

      setAssistantStreaming: (panelId, msgId, streaming) =>
        set((s) => ({
          panels: s.panels.map((p) => {
            if (p.id !== panelId) return p
            return {
              ...p,
              messages: p.messages.map((m) =>
                m.id === msgId ? { ...m, streaming } : m,
              ),
            }
          }),
        })),

      replaceAssistantMessageByAnswerGroup: (panelId, answerGroupId, patch) =>
        set((s) => ({
          panels: s.panels.map((p) => {
            if (p.id !== panelId) return p
            return {
              ...p,
              messages: p.messages.map((m) =>
                m.role === 'assistant' && m.answerGroupId === answerGroupId
                  ? { ...m, ...patch }
                  : m,
              ),
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
      setEnabledMcpServers: (servers) =>
        set({
          enabledMcpServers: Array.from(
            new Set(
              servers
                .map((item) => String(item || '').trim())
                .filter((item) => item.length > 0),
            ),
          ),
        }),
      toggleAttachmentWorkspace: () =>
        set((s) => ({
          attachmentWorkspaceOpen: !s.attachmentWorkspaceOpen,
          memoryWorkspaceOpen: s.attachmentWorkspaceOpen ? s.memoryWorkspaceOpen : false,
        })),
      setAttachmentWorkspaceOpen: (open) =>
        set((s) => ({
          attachmentWorkspaceOpen: open,
          memoryWorkspaceOpen: open ? false : s.memoryWorkspaceOpen,
        })),
      toggleMemoryWorkspace: () =>
        set((s) => ({
          memoryWorkspaceOpen: !s.memoryWorkspaceOpen,
          attachmentWorkspaceOpen: s.memoryWorkspaceOpen ? s.attachmentWorkspaceOpen : false,
        })),
      setMemoryWorkspaceOpen: (open) =>
        set((s) => ({
          memoryWorkspaceOpen: open,
          attachmentWorkspaceOpen: open ? false : s.attachmentWorkspaceOpen,
        })),
      setWelcomeGuideDismissed: (dismissed) => set({ welcomeGuideDismissed: dismissed }),
      setJumpTarget: (target) => set({ jumpTarget: target }),
      clearJumpTarget: () => set({ jumpTarget: null }),
      pushComposerSeed: (seed) =>
        set((s) => ({
          composerSeed: {
            token: s.composerSeed.token + 1,
            text: seed.text ?? '',
            images: seed.images ?? [],
            files: seed.files ?? [],
            editAnswerGroupId: seed.editAnswerGroupId ?? null,
          },
        })),
      setActivePromptId: (id) => set({ activePromptId: id }),
      setTheme: (theme) => set({ theme }),
      toggleTheme: () =>
        set((s) => ({
          theme:
            s.theme === 'dark' ? 'light' : s.theme === 'light' ? 'system' : 'dark',
        })),
      setBookmarks: (bookmarks) =>
        set((s) => {
          const remoteBookmarks = sortBookmarks(
            bookmarks.map((bookmark) =>
              normalizeBookmarkMessage({
                ...bookmark,
                source: 'remote',
              }),
            ),
          )
          const legacyLocalBookmarks = s.bookmarks.filter((bookmark) => bookmark.source === 'local')
          const merged = [
            ...remoteBookmarks,
            ...legacyLocalBookmarks.filter(
              (localBookmark) =>
                !remoteBookmarks.some((remoteBookmark) =>
                  sameBookmarkTarget(remoteBookmark, localBookmark),
                ),
            ),
          ]
          return { bookmarks: sortBookmarks(merged) }
        }),
      addBookmark: (msg) =>
        set((s) => ({
          bookmarks: sortBookmarks([
            normalizeBookmarkMessage(msg),
            ...s.bookmarks.filter(
              (bookmark) =>
                bookmark.id !== msg.id &&
                !sameBookmarkTarget(bookmark, normalizeBookmarkMessage(msg)),
            ),
          ]),
        })),
      removeBookmark: (id) =>
        set((s) => ({ bookmarks: s.bookmarks.filter((b) => b.id !== id) })),
      isBookmarked: (id) => {
        // 这个方法在 render 中调用，直接读 state
        return false // 占位，实际通过 selector 使用
      },
    }),
    {
      name: 'ai-kb-chat-store',
      version: 10,
      migrate: (persistedState) => {
        const state = (persistedState ?? {}) as Partial<ChatState>
        return {
          currentWorkspaceId: state.currentWorkspaceId ?? null,
          sidebarOpen: state.sidebarOpen ?? true,
          webSearchEnabled: state.webSearchEnabled ?? false,
          knowledgeBaseEnabled: state.knowledgeBaseEnabled ?? true,
          enabledMcpServers:
            Array.isArray(state.enabledMcpServers) && state.enabledMcpServers.length > 0
              ? state.enabledMcpServers
                  .map((item) => String(item || '').trim())
                  .filter((item) => item.length > 0)
              : ['knowledge-base', 'web-search'],
          welcomeGuideDismissed: state.welcomeGuideDismissed ?? false,
          activePromptId: state.activePromptId ?? null,
          theme:
            state.theme === 'dark' || state.theme === 'light' || state.theme === 'system'
              ? state.theme
              : 'system',
          bookmarks: sortBookmarks(
            (state.bookmarks ?? []).map((bookmark, index) =>
              normalizeBookmarkMessage({
                ...(bookmark as BookmarkedMessage),
                id:
                  typeof bookmark.id === 'string' && bookmark.id.trim()
                    ? bookmark.id
                    : `legacy-bookmark-${index}`,
                messageId:
                  typeof (bookmark as BookmarkedMessage).messageId === 'number'
                    ? (bookmark as BookmarkedMessage).messageId
                    : undefined,
                answerGroupId:
                  typeof (bookmark as BookmarkedMessage).answerGroupId === 'string'
                    ? (bookmark as BookmarkedMessage).answerGroupId
                    : '',
                source:
                  (bookmark as BookmarkedMessage).source === 'remote'
                    ? 'remote'
                    : 'local',
              }),
            ),
          ),
          memoryWorkspaceOpen: false,
          modelPresets: (state.modelPresets ?? []).map((preset, index) => {
            const createdAt = typeof preset.createdAt === 'number' ? preset.createdAt : Date.now() + index
            const updatedAt = typeof preset.updatedAt === 'number' ? preset.updatedAt : createdAt
            return {
              id: preset.id || `preset-migrated-${index}`,
              name: preset.name || `Preset ${index + 1}`,
              modelConfig: normalizeModelConfig({
                ...preset.modelConfig,
                panel_id:
                  preset.modelConfig?.panel_id ??
                  `preset-migrated-${index}`,
              }),
              createdAt,
              updatedAt,
            }
          }),
          cloudModelProfiles: (state.cloudModelProfiles ?? []).map((profile, index) => {
            const createdAt =
              typeof profile.createdAt === 'number' ? profile.createdAt : Date.now() + index
            const updatedAt =
              typeof profile.updatedAt === 'number' ? profile.updatedAt : createdAt
            return {
              id: profile.id || `cloud-profile-migrated-${index}`,
              name: profile.name || `云端模型 ${index + 1}`,
              modelConfig: normalizeModelConfig({
                ...profile.modelConfig,
                panel_id: profile.modelConfig?.panel_id ?? `cloud-profile-migrated-${index}`,
                connection_type: 'openai_compatible',
                provider: 'openai_compatible',
              }),
              createdAt,
              updatedAt,
            }
          }),
          panels: (state.panels ?? [newPanel()]).map((panel) => ({
            ...panel,
            messages: [],
            modelConfig: (() => {
              const normalized = normalizeModelConfig({
                ...panel.modelConfig,
                panel_id: panel.id,
              })
              if (
                normalized.connection_type === 'ollama' &&
                normalized.model === 'qwen3.5:4b'
              ) {
                return {
                  ...normalized,
                  model: 'qwen3.5-2B:latest',
                }
              }
              return normalized
            })(),
          })),
        }
      },
      partialize: (s) => ({
        currentWorkspaceId: s.currentWorkspaceId,
        sidebarOpen: s.sidebarOpen,
        webSearchEnabled: s.webSearchEnabled,
        knowledgeBaseEnabled: s.knowledgeBaseEnabled,
        enabledMcpServers: s.enabledMcpServers,
        welcomeGuideDismissed: s.welcomeGuideDismissed,
        activePromptId: s.activePromptId,
        theme: s.theme,
        bookmarks: s.bookmarks,
        memoryWorkspaceOpen: false,
        modelPresets: s.modelPresets,
        cloudModelProfiles: s.cloudModelProfiles,
        panels: s.panels.map((p) => ({ ...p, messages: [] })),
      }),
    },
  ),
)
