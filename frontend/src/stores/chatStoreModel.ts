import type {
  Bookmark,
  ChatFile,
  ChatImage,
  ModelConfig,
  Session,
  Workspace,
} from '../api/client'
import { normalizeModelConfig } from '../api/client'
import {
  normalizeBookmarkMessage,
  sameBookmarkTarget,
  sortBookmarks,
} from './chatMigrations'
import type { Panel } from './chatPanelModel'

export {
  defaultEnabledMcpServers,
  migrateChatStoreState,
  normalizeBookmarkMessage,
  normalizeEnabledMcpServers,
  partializeChatStoreState,
  sameBookmarkTarget,
  sortBookmarks,
} from './chatMigrations'
export {
  addErrorMessageToPanels,
  addPanelToList,
  addUserMessageToPanels,
  addUserMessageToPanelState,
  appendChunkToPanel,
  clearMessagesFromPanelList,
  clearMessagesFromPanels,
  createMessageActions,
  defaultModelConfig,
  loadMessagesIntoAllPanels,
  loadMessagesIntoPanel,
  newPanel,
  normalizePanels,
  removeMessageFromPanel,
  removePanelFromList,
  replaceAssistantMessageByAnswerGroupInPanel,
  sanitizePersistedModelConfig,
  setAssistantMessageInPanel,
  setAssistantStreamingInPanel,
  setSourcesInPanel,
  setTaskIdInPanel,
  truncateAnswerGroupFromPanels,
  updateMessageInPanel,
  updatePanelModelConfig,
} from './chatPanelModel'
export type { MessageActionSlice, MessageStateSlice, Panel } from './chatPanelModel'
export {
  appendChunkToMessages,
  createErrorMessage,
  createUserMessage,
  mapMessages,
  removeMessageFromMessages,
  replaceAssistantMessageByAnswerGroup,
  setAssistantMessageInMessages,
  setAssistantStreamingInMessages,
  setSourcesInMessages,
  setTaskIdInMessages,
  truncatePanelMessagesFromAnswerGroup,
  updateMessageInMessages,
} from './chatMessageModel'
export type {
  AssistantAnswerGroupPatch,
  AssistantMessageMeta,
  BuildErrorMessageOptions,
  BuildUserMessageOptions,
  ErrorMessageMeta,
  ErrorRetryMode,
  PanelMessage,
  UserMessagePatch,
} from './chatMessageModel'

export type ResearchMode = 'quick' | 'deep'
export type ThemeMode = 'dark' | 'light' | 'system'
export type AppLanguage = 'zh-CN' | 'en-US'
export type BookmarkedMessage = Bookmark

export interface BookmarkStateSlice {
  bookmarks: BookmarkedMessage[]
}

export interface BookmarkActionSlice {
  setBookmarks: (bookmarks: BookmarkedMessage[]) => void
  addBookmark: (msg: BookmarkedMessage) => void
  removeBookmark: (id: string) => void
  isBookmarked: (id: string) => boolean
}

type BookmarkStateWriter<State extends BookmarkStateSlice> = (
  updater: (state: State) => Pick<State, 'bookmarks'>,
) => void

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

export interface ComposerSeed {
  token: number
  text: string
  images: ChatImage[]
  files: ChatFile[]
  editAnswerGroupId: string | null
}

export interface ChatStorePersistedState {
  currentWorkspaceId: string | null
  sidebarOpen: boolean
  webSearchEnabled: boolean
  knowledgeBaseEnabled: boolean
  researchMode: ResearchMode
  enabledMcpServers: string[]
  welcomeGuideDismissed: boolean
  activePromptId: string | null
  activeAssistantPresetId?: string | null
  theme: ThemeMode
  language: AppLanguage
  bookmarks: BookmarkedMessage[]
  memoryWorkspaceOpen: boolean
  modelPresets: ModelPreset[]
  cloudModelProfiles: CloudModelProfile[]
  panels: Panel[]
}

interface SaveModelPresetOptions {
  now?: () => number
  randomSuffix?: () => string
}

interface SaveCloudModelProfileOptions {
  now?: () => number
  randomSuffix?: () => string
}

export interface CloudModelProfileInput {
  id?: string
  name: string
  modelConfig: ModelConfig
}

export function defaultComposerSeed(): ComposerSeed {
  return {
    token: 0,
    text: '',
    images: [],
    files: [],
    editAnswerGroupId: null,
  }
}

function defaultRandomSuffix(): string {
  return Math.random().toString(36).slice(2, 7)
}

export function sortSessionsByUpdatedAt(sessions: Session[]): Session[] {
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

export function sortWorkspaces(workspaces: Workspace[]): Workspace[] {
  return [...workspaces].sort((a, b) => {
    if (a.is_active !== b.is_active) return a.is_active ? -1 : 1
    return b.updated_at - a.updated_at
  })
}

export function upsertWorkspace(
  workspaces: Workspace[],
  workspace: Workspace,
): Workspace[] {
  return sortWorkspaces([
    workspace,
    ...workspaces.filter((item) => item.workspace_id !== workspace.workspace_id),
  ])
}

export function patchWorkspace(
  workspaces: Workspace[],
  workspaceId: string,
  patch: Partial<Workspace>,
): Workspace[] {
  return sortWorkspaces(
    workspaces.map((workspace) =>
      workspace.workspace_id === workspaceId ? { ...workspace, ...patch } : workspace,
    ),
  )
}

export function adjustWorkspaceSessionCount(
  workspaces: Workspace[],
  workspaceId: string,
  delta: number,
): Workspace[] {
  return sortWorkspaces(
    workspaces.map((workspace) =>
      workspace.workspace_id === workspaceId
        ? {
            ...workspace,
            session_count: Math.max(0, workspace.session_count + delta),
          }
        : workspace,
    ),
  )
}

export function addSessionToList(
  sessions: Session[],
  session: Session,
): Session[] {
  return sortSessionsByUpdatedAt([session, ...sessions])
}

export function removeSessionFromList(
  sessions: Session[],
  sessionId: string,
): Session[] {
  return sessions.filter((session) => session.session_id !== sessionId)
}

export function patchSession(
  sessions: Session[],
  sessionId: string,
  patch: Partial<Session>,
): Session[] {
  return sortSessionsByUpdatedAt(
    sessions.map((session) =>
      session.session_id === sessionId ? { ...session, ...patch } : session,
    ),
  )
}

export function removeModelPresetById(
  modelPresets: ModelPreset[],
  presetId: string,
): ModelPreset[] {
  return modelPresets.filter((preset) => preset.id !== presetId)
}

export function removeCloudModelProfileById(
  cloudModelProfiles: CloudModelProfile[],
  profileId: string,
): CloudModelProfile[] {
  return cloudModelProfiles.filter((profile) => profile.id !== profileId)
}

export function getNextTheme(theme: ThemeMode): ThemeMode {
  return theme === 'dark' ? 'light' : theme === 'light' ? 'system' : 'dark'
}

export function getNextLanguage(language: AppLanguage): AppLanguage {
  return language === 'zh-CN' ? 'en-US' : 'zh-CN'
}

export function toggleAttachmentWorkspaceState(state: {
  attachmentWorkspaceOpen: boolean
  memoryWorkspaceOpen: boolean
}): Pick<typeof state, 'attachmentWorkspaceOpen' | 'memoryWorkspaceOpen'> {
  const attachmentWorkspaceOpen = !state.attachmentWorkspaceOpen
  return {
    attachmentWorkspaceOpen,
    memoryWorkspaceOpen: attachmentWorkspaceOpen ? false : state.memoryWorkspaceOpen,
  }
}

export function setAttachmentWorkspaceState(
  state: { memoryWorkspaceOpen: boolean },
  open: boolean,
): Pick<
  { attachmentWorkspaceOpen: boolean; memoryWorkspaceOpen: boolean },
  'attachmentWorkspaceOpen' | 'memoryWorkspaceOpen'
> {
  return {
    attachmentWorkspaceOpen: open,
    memoryWorkspaceOpen: open ? false : state.memoryWorkspaceOpen,
  }
}

export function toggleMemoryWorkspaceState(state: {
  attachmentWorkspaceOpen: boolean
  memoryWorkspaceOpen: boolean
}): Pick<typeof state, 'attachmentWorkspaceOpen' | 'memoryWorkspaceOpen'> {
  const memoryWorkspaceOpen = !state.memoryWorkspaceOpen
  return {
    memoryWorkspaceOpen,
    attachmentWorkspaceOpen: memoryWorkspaceOpen ? false : state.attachmentWorkspaceOpen,
  }
}

export function setMemoryWorkspaceState(
  state: { attachmentWorkspaceOpen: boolean },
  open: boolean,
): Pick<
  { attachmentWorkspaceOpen: boolean; memoryWorkspaceOpen: boolean },
  'attachmentWorkspaceOpen' | 'memoryWorkspaceOpen'
> {
  return {
    memoryWorkspaceOpen: open,
    attachmentWorkspaceOpen: open ? false : state.attachmentWorkspaceOpen,
  }
}

export function buildComposerSeed(
  current: ComposerSeed,
  seed: {
    text?: string
    images?: ChatImage[]
    files?: ChatFile[]
    editAnswerGroupId?: string | null
  },
): ComposerSeed {
  return {
    token: current.token + 1,
    text: seed.text ?? '',
    images: seed.images ?? [],
    files: seed.files ?? [],
    editAnswerGroupId: seed.editAnswerGroupId ?? null,
  }
}

export function removeBookmarkById(
  bookmarks: BookmarkedMessage[],
  id: string,
): BookmarkedMessage[] {
  return bookmarks.filter((bookmark) => bookmark.id !== id)
}

export function hasBookmark(
  bookmarks: BookmarkedMessage[],
  id: string,
): boolean {
  return bookmarks.some((bookmark) => bookmark.id === id)
}

export function mergeRemoteBookmarksWithLocalLegacy(
  bookmarks: BookmarkedMessage[],
  existingBookmarks: BookmarkedMessage[],
): BookmarkedMessage[] {
  const remoteBookmarks = sortBookmarks(
    bookmarks.map((bookmark) =>
      normalizeBookmarkMessage({
        ...bookmark,
        source: 'remote',
      }),
    ),
  )
  const legacyLocalBookmarks = existingBookmarks.filter(
    (bookmark) => bookmark.source === 'local',
  )
  const merged = [
    ...remoteBookmarks,
    ...legacyLocalBookmarks.filter(
      (localBookmark) =>
        !remoteBookmarks.some((remoteBookmark) =>
          sameBookmarkTarget(remoteBookmark, localBookmark),
        ),
    ),
  ]
  return sortBookmarks(merged)
}

export function addOrReplaceBookmark(
  bookmarks: BookmarkedMessage[],
  bookmark: BookmarkedMessage,
): BookmarkedMessage[] {
  const normalizedBookmark = normalizeBookmarkMessage(bookmark)
  return sortBookmarks([
    normalizedBookmark,
    ...bookmarks.filter(
      (item) =>
        item.id !== bookmark.id &&
        !sameBookmarkTarget(item, normalizedBookmark),
    ),
  ])
}

export function createBookmarkActions<State extends BookmarkStateSlice>(
  set: BookmarkStateWriter<State>,
  get: () => State,
): BookmarkActionSlice {
  return {
    setBookmarks: (bookmarks) =>
      set((state) => ({
        bookmarks: mergeRemoteBookmarksWithLocalLegacy(bookmarks, state.bookmarks),
      })),
    addBookmark: (bookmark) =>
      set((state) => ({
        bookmarks: addOrReplaceBookmark(state.bookmarks, bookmark),
      })),
    removeBookmark: (id) =>
      set((state) => ({
        bookmarks: removeBookmarkById(state.bookmarks, id),
      })),
    isBookmarked: (id) => hasBookmark(get().bookmarks, id),
  }
}

export function saveModelPreset(
  modelPresets: ModelPreset[],
  name: string,
  modelConfig: ModelConfig,
  options: SaveModelPresetOptions = {},
): ModelPreset[] {
  const trimmedName = name.trim()
  if (!trimmedName) return modelPresets

  const now = (options.now ?? Date.now)()
  const normalizedModelConfig = normalizeModelConfig({
    ...modelConfig,
    panel_id: modelConfig.panel_id || `preset-${now}`,
  })
  const existingPreset = modelPresets.find(
    (preset) => preset.name.toLowerCase() === trimmedName.toLowerCase(),
  )

  if (existingPreset) {
    return modelPresets.map((preset) =>
      preset.id === existingPreset.id
        ? {
            ...preset,
            name: trimmedName,
            modelConfig: normalizedModelConfig,
            updatedAt: now,
          }
        : preset,
    )
  }

  const randomSuffix = (options.randomSuffix ?? defaultRandomSuffix)()
  return [
    {
      id: `preset-${now}-${randomSuffix}`,
      name: trimmedName,
      modelConfig: normalizedModelConfig,
      createdAt: now,
      updatedAt: now,
    },
    ...modelPresets,
  ]
}

export function applyModelPresetToPanels(
  panels: Panel[],
  modelPresets: ModelPreset[],
  panelId: string,
  presetId: string,
): Panel[] {
  const preset = modelPresets.find((item) => item.id === presetId)
  if (!preset) return panels

  return panels.map((panel) =>
    panel.id === panelId
      ? {
          ...panel,
          modelConfig: normalizeModelConfig({
            ...preset.modelConfig,
            panel_id: panelId,
          }),
        }
      : panel,
  )
}

export function saveCloudModelProfile(
  cloudModelProfiles: CloudModelProfile[],
  profile: CloudModelProfileInput,
  options: SaveCloudModelProfileOptions = {},
): CloudModelProfile[] {
  const trimmedName = profile.name.trim()
  if (!trimmedName) return cloudModelProfiles

  const now = (options.now ?? Date.now)()
  const normalizedModelConfig = normalizeModelConfig({
    ...profile.modelConfig,
    panel_id: profile.modelConfig.panel_id || `cloud-profile-${now}`,
    connection_type: 'openai_compatible',
    provider: 'openai_compatible',
  })
  const existingProfile = profile.id
    ? cloudModelProfiles.find((item) => item.id === profile.id)
    : cloudModelProfiles.find(
        (item) => item.name.toLowerCase() === trimmedName.toLowerCase(),
      )

  if (existingProfile) {
    return cloudModelProfiles.map((item) =>
      item.id === existingProfile.id
        ? {
            ...item,
            name: trimmedName,
            modelConfig: normalizedModelConfig,
            updatedAt: now,
          }
        : item,
    )
  }

  const randomSuffix = (options.randomSuffix ?? defaultRandomSuffix)()
  return [
    {
      id: `cloud-profile-${now}-${randomSuffix}`,
      name: trimmedName,
      modelConfig: normalizedModelConfig,
      createdAt: now,
      updatedAt: now,
    },
    ...cloudModelProfiles,
  ]
}

export function applyCloudModelProfileToPanels(
  panels: Panel[],
  cloudModelProfiles: CloudModelProfile[],
  panelId: string,
  profileId: string,
): Panel[] {
  const profile = cloudModelProfiles.find((item) => item.id === profileId)
  if (!profile) return panels

  return panels.map((panel) =>
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
  )
}
