import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  ChatFile,
  ChatImage,
  ModelConfig,
  Session,
  Workspace,
  Message,
} from '../api/client'
import {
  addPanelToList,
  addSessionToList,
  adjustWorkspaceSessionCount,
  applyCloudModelProfileToPanels,
  applyModelPresetToPanels,
  buildComposerSeed,
  defaultComposerSeed,
  defaultEnabledMcpServers,
  getNextLanguage,
  getNextTheme,
  loadMessagesIntoAllPanels,
  migrateChatStoreState,
  newPanel,
  normalizeEnabledMcpServers,
  normalizePanels,
  patchSession,
  patchWorkspace,
  partializeChatStoreState,
  removePanelFromList,
  removeSessionFromList,
  removeCloudModelProfileById,
  removeModelPresetById,
  saveCloudModelProfile as saveCloudModelProfileModel,
  saveModelPreset as saveModelPresetModel,
  setAttachmentWorkspaceState,
  setMemoryWorkspaceState,
  sortSessionsByUpdatedAt,
  sortWorkspaces,
  toggleAttachmentWorkspaceState,
  toggleMemoryWorkspaceState,
  createBookmarkActions,
  createMessageActions,
  updatePanelModelConfig,
  upsertWorkspace,
} from './chatStoreModel'
import type {
  AppLanguage,
  BookmarkActionSlice,
  BookmarkedMessage,
  ChatStorePersistedState,
  CloudModelProfile,
  ComposerSeed,
  ErrorRetryMode,
  MessageActionSlice,
  ModelPreset,
  Panel,
  PanelMessage,
  ResearchMode,
  ThemeMode,
} from './chatStoreModel'

export type {
  AppLanguage,
  BookmarkedMessage,
  ChatStorePersistedState,
  CloudModelProfile,
  ComposerSeed,
  ErrorRetryMode,
  ModelPreset,
  Panel,
  PanelMessage,
  ResearchMode,
  ThemeMode,
}

export interface JumpTarget {
  sessionId: string
  role: 'user' | 'assistant'
  panelId?: string
  answerGroupId?: string
  messageId?: number
  searchQuery?: string
}

interface ChatState extends BookmarkActionSlice, MessageActionSlice {
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
  researchMode: ResearchMode
  enabledMcpServers: string[]
  attachmentWorkspaceOpen: boolean
  memoryWorkspaceOpen: boolean
  welcomeGuideDismissed: boolean
  composerSeed: ComposerSeed
  jumpTarget: JumpTarget | null

  // Active system prompt id (null = use default)
  activePromptId: string | null
  activeAssistantPresetId: string | null

  // Theme and language
  theme: ThemeMode
  language: AppLanguage

  // Bookmark messages
  bookmarks: BookmarkedMessage[]

  // Session actions
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

  // Panel actions
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

  // UI actions
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  setSettingsOpen: (open: boolean) => void
  setWebSearchEnabled: (enabled: boolean) => void
  setKnowledgeBaseEnabled: (enabled: boolean) => void
  setResearchMode: (mode: ResearchMode) => void
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
  setActiveAssistantPresetId: (id: string | null) => void
  setTheme: (theme: ThemeMode) => void
  toggleTheme: () => void
  setLanguage: (language: AppLanguage) => void
  toggleLanguage: () => void
}

export const useChatStore = create<ChatState>()(
  persist<ChatState, [], [], ChatStorePersistedState>(
    (set, get) => ({
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
      researchMode: 'deep',
      enabledMcpServers: defaultEnabledMcpServers(),
      attachmentWorkspaceOpen: false,
      memoryWorkspaceOpen: false,
      welcomeGuideDismissed: false,
      jumpTarget: null,
      composerSeed: defaultComposerSeed(),
      activePromptId: null,
      activeAssistantPresetId: null,
      theme: 'system',
      language: 'zh-CN',
      bookmarks: [],

      setWorkspaces: (workspaces) => set({ workspaces: sortWorkspaces(workspaces) }),
      setCurrentWorkspace: (id) => set({ currentWorkspaceId: id }),
      addWorkspace: (workspace) =>
        set((s) => ({
          workspaces: upsertWorkspace(s.workspaces, workspace),
        })),
      updateWorkspace: (workspaceId, patch) =>
        set((s) => ({
          workspaces: patchWorkspace(s.workspaces, workspaceId, patch),
        })),
      adjustWorkspaceSessionCount: (workspaceId, delta) =>
        set((s) => ({
          workspaces: adjustWorkspaceSessionCount(s.workspaces, workspaceId, delta),
        })),
      setSessions: (sessions) => set({ sessions: sortSessionsByUpdatedAt(sessions) }),
      setCurrentSession: (id) => set({ currentSessionId: id }),
      addSession: (session) =>
        set((s) => ({ sessions: addSessionToList(s.sessions, session) })),
      removeSession: (id) =>
        set((s) => ({ sessions: removeSessionFromList(s.sessions, id) })),
      updateSessionTitle: (id, title) =>
        set((s) => ({
          sessions: patchSession(s.sessions, id, { title }),
        })),
      updateSession: (id, patch) =>
        set((s) => ({
          sessions: patchSession(s.sessions, id, patch),
        })),

      addPanel: () =>
        set((s) => ({ panels: addPanelToList(s.panels) })),
      removePanel: (panelId) =>
        set((s) => ({ panels: removePanelFromList(s.panels, panelId) })),
      updatePanelModel: (panelId, config) =>
        set((s) => ({
          panels: updatePanelModelConfig(s.panels, panelId, config),
        })),
      saveModelPreset: (name, modelConfig) =>
        set((s) => ({
          modelPresets: saveModelPresetModel(s.modelPresets, name, modelConfig),
        })),
      deleteModelPreset: (presetId) =>
        set((s) => ({
          modelPresets: removeModelPresetById(s.modelPresets, presetId),
        })),
      applyModelPreset: (panelId, presetId) =>
        set((s) => ({
          panels: applyModelPresetToPanels(s.panels, s.modelPresets, panelId, presetId),
        })),
      saveCloudModelProfile: ({ id, name, modelConfig }) =>
        set((s) => ({
          cloudModelProfiles: saveCloudModelProfileModel(s.cloudModelProfiles, {
            id,
            name,
            modelConfig,
          }),
        })),
      deleteCloudModelProfile: (profileId) =>
        set((s) => ({
          cloudModelProfiles: removeCloudModelProfileById(s.cloudModelProfiles, profileId),
        })),
      applyCloudModelProfile: (panelId, profileId) =>
        set((s) => ({
          panels: applyCloudModelProfileToPanels(
            s.panels,
            s.cloudModelProfiles,
            panelId,
            profileId,
          ),
        })),
      setPanels: (panels) =>
        set({
          panels: normalizePanels(panels),
        }),
      loadMessagesToAllPanels: (messages) =>
        set((s) => ({
          panels: loadMessagesIntoAllPanels(s.panels, messages),
        })),

      ...createMessageActions(set),

      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      setSettingsOpen: (open) => set({ settingsOpen: open }),
      setWebSearchEnabled: (enabled) => set({ webSearchEnabled: enabled }),
      setKnowledgeBaseEnabled: (enabled) => set({ knowledgeBaseEnabled: enabled }),
      setResearchMode: (mode) => set({ researchMode: mode }),
      setEnabledMcpServers: (servers) =>
        set({
          enabledMcpServers: normalizeEnabledMcpServers(servers),
        }),
      toggleAttachmentWorkspace: () =>
        set((s) => toggleAttachmentWorkspaceState(s)),
      setAttachmentWorkspaceOpen: (open) =>
        set((s) => setAttachmentWorkspaceState(s, open)),
      toggleMemoryWorkspace: () =>
        set((s) => toggleMemoryWorkspaceState(s)),
      setMemoryWorkspaceOpen: (open) =>
        set((s) => setMemoryWorkspaceState(s, open)),
      setWelcomeGuideDismissed: (dismissed) => set({ welcomeGuideDismissed: dismissed }),
      setJumpTarget: (target) => set({ jumpTarget: target }),
      clearJumpTarget: () => set({ jumpTarget: null }),
      pushComposerSeed: (seed) =>
        set((s) => ({ composerSeed: buildComposerSeed(s.composerSeed, seed) })),
      setActivePromptId: (id) => set({ activePromptId: id }),
      setActiveAssistantPresetId: (id) => set({ activeAssistantPresetId: id }),
      setTheme: (theme) => set({ theme }),
      toggleTheme: () =>
        set((s) => ({
          theme: getNextTheme(s.theme),
        })),
      setLanguage: (language) => set({ language }),
      toggleLanguage: () =>
        set((s) => ({
          language: getNextLanguage(s.language),
        })),
      ...createBookmarkActions(set, get),
    }),
    {
      name: 'ai-kb-chat-store',
      version: 12,
      migrate: (persistedState) => migrateChatStoreState(persistedState),
      partialize: partializeChatStoreState,
    },
  ),
)
