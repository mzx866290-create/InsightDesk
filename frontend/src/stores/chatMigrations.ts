import { normalizeModelConfig } from '../api/client'
import type {
  BookmarkedMessage,
  ChatStorePersistedState,
  CloudModelProfile,
  ModelPreset,
} from './chatStoreModel'
import { newPanel, sanitizePersistedModelConfig } from './chatPanelModel'
import type { Panel } from './chatPanelModel'

interface MigrateChatStoreOptions {
  now?: () => number
  createPanel?: () => Panel
}

export function defaultEnabledMcpServers(): string[] {
  return []
}

export function normalizeEnabledMcpServers(servers: string[]): string[] {
  return Array.from(
    new Set(
      servers
        .map((item) => String(item || '').trim())
        .filter((item) => item.length > 0),
    ),
  )
}

export function normalizeBookmarkMessage(bookmark: BookmarkedMessage): BookmarkedMessage {
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

export function sameBookmarkTarget(
  a: BookmarkedMessage,
  b: BookmarkedMessage,
): boolean {
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

export function sortBookmarks(bookmarks: BookmarkedMessage[]): BookmarkedMessage[] {
  return [...bookmarks].sort((a, b) => {
    const aTs = a.updatedAt ?? a.createdAt
    const bTs = b.updatedAt ?? b.createdAt
    return bTs - aTs
  })
}

function normalizePersistedBookmarks(
  bookmarks: unknown,
): BookmarkedMessage[] {
  const rawBookmarks = Array.isArray(bookmarks) ? bookmarks : []
  return sortBookmarks(
    rawBookmarks.map((bookmark, index) =>
      normalizeBookmarkMessage({
        ...(bookmark as BookmarkedMessage),
        id:
          typeof (bookmark as BookmarkedMessage).id === 'string' &&
          (bookmark as BookmarkedMessage).id.trim()
            ? (bookmark as BookmarkedMessage).id
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
  )
}

function migrateModelPresets(
  modelPresets: unknown,
  now: () => number,
): ModelPreset[] {
  const rawPresets = Array.isArray(modelPresets) ? modelPresets : []
  return rawPresets.map((preset, index) => {
    const item = preset as Partial<ModelPreset>
    const createdAt = typeof item.createdAt === 'number' ? item.createdAt : now() + index
    const updatedAt = typeof item.updatedAt === 'number' ? item.updatedAt : createdAt
    return {
      id: item.id || `preset-migrated-${index}`,
      name: item.name || `Preset ${index + 1}`,
      modelConfig: sanitizePersistedModelConfig(
        normalizeModelConfig({
          ...item.modelConfig,
          panel_id:
            item.modelConfig?.panel_id ??
            `preset-migrated-${index}`,
        }),
      ),
      createdAt,
      updatedAt,
    }
  })
}

function migrateCloudModelProfiles(
  cloudModelProfiles: unknown,
  now: () => number,
): CloudModelProfile[] {
  const rawProfiles = Array.isArray(cloudModelProfiles) ? cloudModelProfiles : []
  return rawProfiles.map((profile, index) => {
    const item = profile as Partial<CloudModelProfile>
    const createdAt = typeof item.createdAt === 'number' ? item.createdAt : now() + index
    const updatedAt = typeof item.updatedAt === 'number' ? item.updatedAt : createdAt
    return {
      id: item.id || `cloud-profile-migrated-${index}`,
      name: item.name || `云端模型 ${index + 1}`,
      modelConfig: sanitizePersistedModelConfig(
        normalizeModelConfig({
          ...item.modelConfig,
          panel_id: item.modelConfig?.panel_id ?? `cloud-profile-migrated-${index}`,
          connection_type: 'openai_compatible',
          provider: 'openai_compatible',
        }),
      ),
      createdAt,
      updatedAt,
    }
  })
}

function migratePanels(
  panels: unknown,
  createPanel: () => Panel,
): Panel[] {
  const rawPanels = Array.isArray(panels) && panels.length > 0 ? panels : [createPanel()]
  return rawPanels.map((panel) => {
    const item = panel as Panel
    return {
      ...item,
      messages: [],
      modelConfig: (() => {
        const normalized = normalizeModelConfig({
          ...item.modelConfig,
          panel_id: item.id,
        })
        if (
          normalized.connection_type === 'ollama' &&
          normalized.model === 'qwen3.5:4b'
        ) {
          return sanitizePersistedModelConfig({
            ...normalized,
            model: 'qwen3.5-2B:latest',
          })
        }
        return sanitizePersistedModelConfig(normalized)
      })(),
    }
  })
}

export function migrateChatStoreState(
  persistedState: unknown,
  options: MigrateChatStoreOptions = {},
): ChatStorePersistedState {
  const state = (persistedState ?? {}) as Partial<ChatStorePersistedState>
  const now = options.now ?? Date.now
  const createPanel = options.createPanel ?? newPanel
  const normalizedEnabledMcpServers = Array.isArray(state.enabledMcpServers)
    ? normalizeEnabledMcpServers(state.enabledMcpServers)
    : []
  const enabledMcpServers = Array.isArray(state.enabledMcpServers)
    ? normalizedEnabledMcpServers
    : defaultEnabledMcpServers()

  return {
    currentWorkspaceId: state.currentWorkspaceId ?? null,
    sidebarOpen: state.sidebarOpen ?? true,
    webSearchEnabled: state.webSearchEnabled ?? false,
    knowledgeBaseEnabled: state.knowledgeBaseEnabled ?? true,
    researchMode: state.researchMode === 'quick' ? 'quick' : 'deep',
    researchSourceStrategy:
      state.researchSourceStrategy === 'web_and_community' ||
      state.researchSourceStrategy === 'community_first' ||
      state.researchSourceStrategy === 'evidence_strict'
        ? state.researchSourceStrategy
        : 'web_only',
    enabledMcpServers,
    welcomeGuideDismissed: state.welcomeGuideDismissed ?? false,
    activePromptId: state.activePromptId ?? null,
    activeAssistantPresetId: state.activeAssistantPresetId ?? null,
    theme:
      state.theme === 'dark' || state.theme === 'light' || state.theme === 'system'
        ? state.theme
        : 'system',
    language: state.language === 'en-US' ? 'en-US' : 'zh-CN',
    bookmarks: normalizePersistedBookmarks(state.bookmarks),
    memoryWorkspaceOpen: false,
    modelPresets: migrateModelPresets(state.modelPresets, now),
    cloudModelProfiles: migrateCloudModelProfiles(state.cloudModelProfiles, now),
    panels: migratePanels(state.panels, createPanel),
  }
}

export function partializeChatStoreState(state: ChatStorePersistedState): ChatStorePersistedState {
  return {
    currentWorkspaceId: state.currentWorkspaceId,
    sidebarOpen: state.sidebarOpen,
    webSearchEnabled: state.webSearchEnabled,
    knowledgeBaseEnabled: state.knowledgeBaseEnabled,
    researchMode: state.researchMode,
    researchSourceStrategy: state.researchSourceStrategy,
    enabledMcpServers: state.enabledMcpServers,
    welcomeGuideDismissed: state.welcomeGuideDismissed,
    activePromptId: state.activePromptId,
    activeAssistantPresetId: state.activeAssistantPresetId,
    theme: state.theme,
    language: state.language,
    bookmarks: state.bookmarks,
    memoryWorkspaceOpen: false,
    modelPresets: state.modelPresets.map((preset) => ({
      ...preset,
      modelConfig: sanitizePersistedModelConfig(preset.modelConfig),
    })),
    cloudModelProfiles: state.cloudModelProfiles.map((profile) => ({
      ...profile,
      modelConfig: sanitizePersistedModelConfig(profile.modelConfig),
    })),
    panels: state.panels.map((panel) => ({
      ...panel,
      messages: [],
      modelConfig: sanitizePersistedModelConfig(panel.modelConfig),
    })),
  }
}
