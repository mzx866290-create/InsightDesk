import {
  BASE,
  fetchWithApiToken,
} from './auth'
import {
  normalizeSession,
  normalizeWorkspace,
  normalizeBookmark,
  normalizeRetrievalSourceText,
} from './normalizers'
import type {
  Session,
  Workspace,
  WorkspacePreset,
  SessionMemoryKind,
  MessageFeedbackValue,
  RetrievalFeedbackValue,
  SessionMemory,
  Message,
  SessionPanel,
  SourceItem,
  ChatImage,
  ChatFile,
  SessionAttachment,
  SessionAttachmentSummary,
  TaskRecord,
  MessagesResponse,
  ImportSessionMessagesPayload,
  Bookmark,
  SessionAttachmentsResponse,
  AnswerGroupReviewResponse,
  PromoteAnswerResponse,
  ShareLinkResponse,
} from './types'

const fetch: typeof globalThis.fetch = fetchWithApiToken
// 鈹€鈹€ Sessions 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

export async function getSessions(params?: {
  query?: string
  archived?: boolean
  favorite?: boolean
  tag?: string
  workspace_id?: string
}): Promise<Session[]> {
  const searchParams = new URLSearchParams()
  if (params?.query?.trim()) searchParams.set('query', params.query.trim())
  if (params?.archived !== undefined) searchParams.set('archived', String(params.archived))
  if (params?.favorite !== undefined) searchParams.set('favorite', String(params.favorite))
  if (params?.tag?.trim()) searchParams.set('tag', params.tag.trim())
  if (params?.workspace_id?.trim()) searchParams.set('workspace_id', params.workspace_id.trim())

  const query = searchParams.toString()
  const res = await fetch(`${BASE}/sessions${query ? `?${query}` : ''}`)
  const data = await res.json()
  return (data.sessions as Session[]).map((session) => normalizeSession(session))
}

export async function getWorkspaces(): Promise<{ workspaces: Workspace[]; active_workspace_id: string | null }> {
  const res = await fetch(`${BASE}/workspaces`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as {
    workspaces?: Workspace[]
    active_workspace_id?: string | null
  }
  return {
    workspaces: (data.workspaces ?? []).map((workspace) => normalizeWorkspace(workspace)),
    active_workspace_id: typeof data.active_workspace_id === 'string' && data.active_workspace_id.trim()
      ? data.active_workspace_id
      : null,
  }
}

export async function createWorkspace(payload: {
  name: string
  description?: string
  color?: Workspace['color']
  activate?: boolean
  preset?: Partial<WorkspacePreset>
}): Promise<Workspace> {
  const res = await fetch(`${BASE}/workspaces`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: payload.name,
      description: payload.description ?? '',
      color: payload.color ?? 'blue',
      activate: payload.activate ?? true,
      preset: payload.preset
        ? {
            default_panels: payload.preset.default_panels ?? [],
            tool_config: payload.preset.tool_config ?? {
              web_search_enabled: false,
              knowledge_base_enabled: true,
              mcp_servers_enabled: [],
            },
            output_preset: payload.preset.output_preset ?? {
              deck_theme: 'default',
              target_slide_count: 8,
            },
          }
        : undefined,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as { workspace: Workspace }
  return normalizeWorkspace(data.workspace)
}

export async function updateWorkspace(
  workspaceId: string,
  patch: {
    name?: string
    description?: string
    color?: Workspace['color']
    preset?: Partial<WorkspacePreset>
  },
): Promise<Workspace> {
  const res = await fetch(`${BASE}/workspaces/${encodeURIComponent(workspaceId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...patch,
      preset: patch.preset
        ? {
            default_panels: patch.preset.default_panels ?? [],
            tool_config: patch.preset.tool_config ?? {
              web_search_enabled: false,
              knowledge_base_enabled: true,
              mcp_servers_enabled: [],
            },
            output_preset: patch.preset.output_preset ?? {
              deck_theme: 'default',
              target_slide_count: 8,
            },
          }
        : undefined,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as { workspace: Workspace }
  return normalizeWorkspace(data.workspace)
}

export async function activateWorkspace(workspaceId: string): Promise<Workspace> {
  const res = await fetch(`${BASE}/workspaces/${encodeURIComponent(workspaceId)}/activate`, {
    method: 'POST',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as { workspace: Workspace }
  return normalizeWorkspace(data.workspace)
}

export async function deleteWorkspace(
  workspaceId: string,
  options?: { target_workspace_id?: string },
): Promise<{
  deleted_workspace_id: string
  target_workspace_id: string
  target_workspace?: Workspace
}> {
  const searchParams = new URLSearchParams()
  if (options?.target_workspace_id?.trim()) {
    searchParams.set('target_workspace_id', options.target_workspace_id.trim())
  }
  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : ''
  const res = await fetch(`${BASE}/workspaces/${encodeURIComponent(workspaceId)}${suffix}`, {
    method: 'DELETE',
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    deleted_workspace_id?: string
    target_workspace_id?: string
    target_workspace?: Workspace
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  if (!data.deleted_workspace_id || !data.target_workspace_id) {
    throw new Error('Invalid workspace deletion response.')
  }
  return {
    deleted_workspace_id: data.deleted_workspace_id,
    target_workspace_id: data.target_workspace_id,
    target_workspace: data.target_workspace
      ? normalizeWorkspace(data.target_workspace)
      : undefined,
  }
}

export async function createSession(
  title = '',
  options?: { workspace_id?: string },
): Promise<{ session_id: string; title: string; workspace_id?: string }> {
  const res = await fetch(`${BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title,
      workspace_id: options?.workspace_id,
    }),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    session_id?: string
    title?: string
    workspace_id?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  if (!data.session_id || typeof data.session_id !== 'string') {
    throw new Error('Invalid create session response.')
  }
  return {
    session_id: data.session_id,
    title: typeof data.title === 'string' && data.title.trim() ? data.title : '鏂板缓瀵硅瘽',
    workspace_id:
      typeof data.workspace_id === 'string' && data.workspace_id.trim()
        ? data.workspace_id.trim()
        : undefined,
  }
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`${BASE}/sessions/${sessionId}`, { method: 'DELETE' })
}

export async function getBookmarks(params?: {
  session_id?: string
}): Promise<Bookmark[]> {
  const searchParams = new URLSearchParams()
  if (params?.session_id?.trim()) searchParams.set('session_id', params.session_id.trim())
  const query = searchParams.toString()
  const res = await fetch(`${BASE}/bookmarks${query ? `?${query}` : ''}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as {
    bookmarks?: Array<Partial<Bookmark> & { id: string }>
  }
  return (data.bookmarks ?? []).map((bookmark) => normalizeBookmark(bookmark))
}

export async function createBookmark(payload: {
  session_id: string
  role: 'user' | 'assistant'
  message_id?: number
  panel_id?: string
  answer_group_id?: string
  content?: string
  model_id?: string
  session_title?: string
}): Promise<Bookmark> {
  const res = await fetch(`${BASE}/bookmarks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: payload.session_id,
      role: payload.role,
      message_id: payload.message_id,
      panel_id: payload.panel_id ?? '',
      answer_group_id: payload.answer_group_id ?? '',
      content: payload.content ?? '',
      model_id: payload.model_id ?? '',
      session_title: payload.session_title ?? '',
    }),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    bookmark?: Partial<Bookmark> & { id: string }
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  if (!data.bookmark) {
    throw new Error('Invalid create bookmark response.')
  }
  return normalizeBookmark(data.bookmark)
}

export async function deleteBookmark(bookmarkId: string): Promise<void> {
  const res = await fetch(`${BASE}/bookmarks/${encodeURIComponent(bookmarkId)}`, {
    method: 'DELETE',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
}

export async function updateSessionMeta(
  sessionId: string,
  patch: {
    title?: string
    is_archived?: boolean
    is_favorite?: boolean
    is_pinned?: boolean
    tags?: string[]
    workspace_id?: string
  },
): Promise<Session> {
  const res = await fetch(`${BASE}/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json()
  return normalizeSession(data.session as Session)
}

export async function reorderSessions(
  sessionIds: string[],
  options?: {
    workspace_id?: string
  },
): Promise<Session[]> {
  const normalizedIds = sessionIds
    .map((id) => id.trim())
    .filter((id) => id.length > 0)

  if (normalizedIds.length < 2) {
    throw new Error('At least two sessions are required to reorder.')
  }

  const res = await fetch(`${BASE}/sessions/reorder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_ids: normalizedIds,
      workspace_id: options?.workspace_id,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as {
    sessions?: Session[]
  }
  return (data.sessions ?? []).map((session) => normalizeSession(session))
}

export async function getSessionMessages(sessionId: string): Promise<MessagesResponse> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/messages`)
  const data = await res.json()
  return {
    messages: data.messages as Message[],
    context_limit: data.context_limit ?? 16,
    total_messages: data.total_messages ?? (data.messages as Message[]).length,
    panels: (data.panels ?? []) as SessionPanel[],
    panel_messages: (data.panel_messages ?? {}) as Record<string, Message[]>,
  }
}

export async function importSessionMessages(
  sessionId: string,
  payload: ImportSessionMessagesPayload,
): Promise<MessagesResponse> {
  const res = await fetch(`${BASE}/sessions/${encodeURIComponent(sessionId)}/messages/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    messages?: Message[]
    context_limit?: number
    total_messages?: number
    panels?: SessionPanel[]
    panel_messages?: Record<string, Message[]>
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return {
    messages: (data.messages ?? []) as Message[],
    context_limit: data.context_limit ?? 16,
    total_messages: data.total_messages ?? (data.messages ?? []).length,
    panels: (data.panels ?? []) as SessionPanel[],
    panel_messages: (data.panel_messages ?? {}) as Record<string, Message[]>,
  }
}

export async function setMessageFeedback(
  sessionId: string,
  payload: {
    value: MessageFeedbackValue
    message_id?: number
    panel_id?: string
    answer_group_id?: string
  },
): Promise<{
  message_id: number
  panel_id: string
  answer_group_id: string
  feedback_value: MessageFeedbackValue
}> {
  const res = await fetch(`${BASE}/sessions/${encodeURIComponent(sessionId)}/messages/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      value: payload.value,
      message_id: payload.message_id,
      panel_id: payload.panel_id ?? '',
      answer_group_id: payload.answer_group_id ?? '',
    }),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    feedback?: {
      message_id: number
      panel_id: string
      answer_group_id: string
      feedback_value: MessageFeedbackValue
    }
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  if (!data.feedback) {
    throw new Error('Invalid message feedback response.')
  }
  return data.feedback
}

export async function truncateSessionMessagesFromAnswerGroup(
  sessionId: string,
  payload: {
    answer_group_id: string
    content: string
    images?: ChatImage[]
    files?: ChatFile[]
  },
): Promise<{
  session_id: string
  answer_group_id: string
  anchor_message_id: number
  deleted_count: number
}> {
  const res = await fetch(`${BASE}/sessions/${encodeURIComponent(sessionId)}/messages/truncate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      answer_group_id: payload.answer_group_id,
      content: payload.content,
      images: payload.images ?? [],
      files: payload.files ?? [],
    }),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    result?: {
      session_id: string
      answer_group_id: string
      anchor_message_id: number
      deleted_count: number
    }
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  if (!data.result) {
    throw new Error('Invalid truncate response.')
  }
  return data.result
}

export function buildRetrievalSourceKey(source: SourceItem): string {
  const normalizedType = normalizeRetrievalSourceText(source.type).toLowerCase()
  const normalizedTitle = normalizeRetrievalSourceText(source.title)
  const normalizedUrl = normalizeRetrievalSourceText(source.url)
  const normalizedSnippet = normalizeRetrievalSourceText(source.snippet).slice(0, 200)
  const normalizedIndex = source.index === undefined || source.index === null
    ? ''
    : normalizeRetrievalSourceText(source.index)
  return [
    normalizedType,
    normalizedTitle,
    normalizedUrl,
    normalizedSnippet,
    normalizedIndex,
  ].join('||')
}

export async function setRetrievalFeedback(
  sessionId: string,
  payload: {
    panel_id: string
    answer_group_id: string
    source: SourceItem
    value: RetrievalFeedbackValue
  },
): Promise<{
  source_key: string
  feedback_value: RetrievalFeedbackValue
  updated_at: number
}> {
  const res = await fetch(`${BASE}/sessions/${encodeURIComponent(sessionId)}/retrieval-feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    feedback?: {
      source_key: string
      feedback_value: RetrievalFeedbackValue
      updated_at: number
    }
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  if (!data.feedback) {
    throw new Error('Invalid retrieval feedback response.')
  }
  return data.feedback
}

export async function getRetrievalFeedback(
  sessionId: string,
  panelId: string,
  answerGroupId: string,
): Promise<Array<{
  source_key: string
  feedback_value: RetrievalFeedbackValue
  updated_at: number
}>> {
  const params = new URLSearchParams({
    panel_id: panelId,
    answer_group_id: answerGroupId,
  })
  const res = await fetch(`${BASE}/sessions/${encodeURIComponent(sessionId)}/retrieval-feedback?${params.toString()}`)
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    feedback?: Array<{
      source_key: string
      feedback_value: RetrievalFeedbackValue
      updated_at: number
    }>
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return data.feedback ?? []
}

export async function getSessionMemory(
  sessionId: string,
  kind?: SessionMemoryKind,
): Promise<SessionMemory[]> {
  const query = kind ? `?kind=${encodeURIComponent(kind)}` : ''
  const res = await fetch(`${BASE}/sessions/${encodeURIComponent(sessionId)}/memory${query}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as { memories?: SessionMemory[] }
  return data.memories ?? []
}

export async function pinSessionMemory(
  sessionId: string,
  payload: {
    content: string
    kind?: SessionMemoryKind
  },
): Promise<{ created: boolean; memory: SessionMemory }> {
  const res = await fetch(`${BASE}/sessions/${encodeURIComponent(sessionId)}/memory/pin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content: payload.content,
      kind: payload.kind ?? 'fact',
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as { created: boolean; memory: SessionMemory }
  return {
    created: data.created,
    memory: data.memory,
  }
}

export async function deleteSessionMemory(
  sessionId: string,
  memoryId: string,
): Promise<void> {
  const res = await fetch(
    `${BASE}/sessions/${encodeURIComponent(sessionId)}/memory/${encodeURIComponent(memoryId)}`,
    { method: 'DELETE' },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
}

export async function updateSessionMemory(
  sessionId: string,
  memoryId: string,
  payload: {
    content?: string
    kind?: SessionMemoryKind
  },
): Promise<SessionMemory> {
  const body: {
    content?: string
    kind?: SessionMemoryKind
  } = {}
  if (typeof payload.content === 'string') body.content = payload.content
  if (payload.kind) body.kind = payload.kind

  const res = await fetch(
    `${BASE}/sessions/${encodeURIComponent(sessionId)}/memory/${encodeURIComponent(memoryId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as { memory: SessionMemory }
  return data.memory
}

export async function summarizeSessionMemory(
  sessionId: string,
  options?: { force?: boolean },
): Promise<{ created: boolean; memory: SessionMemory; reason?: string }> {
  const query = options?.force ? '?force=true' : ''
  const res = await fetch(
    `${BASE}/sessions/${encodeURIComponent(sessionId)}/memory/summarize${query}`,
    { method: 'POST' },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as {
    created: boolean
    memory: SessionMemory
    reason?: string
  }
  return {
    created: data.created,
    memory: data.memory,
    reason: data.reason,
  }
}

export async function getSessionAttachments(
  sessionId: string,
  vectorStorePath?: string,
  workspaceId?: string,
): Promise<SessionAttachmentsResponse> {
  const searchParams = new URLSearchParams()
  if (vectorStorePath?.trim()) searchParams.set('vector_store_path', vectorStorePath.trim())
  if (workspaceId?.trim()) searchParams.set('workspace_id', workspaceId.trim())
  const query = searchParams.toString() ? `?${searchParams.toString()}` : ''
  const res = await fetch(`${BASE}/sessions/${sessionId}/attachments${query}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json()
  return {
    session_id: data.session_id as string,
    attachments: (data.attachments ?? []) as SessionAttachment[],
    summary: (data.summary ?? {
      total_attachments: 0,
      file_count: 0,
      image_count: 0,
      text_ready_count: 0,
      reusable_count: 0,
      total_size_bytes: 0,
    }) as SessionAttachmentSummary,
    current_vector_store_path: (data.current_vector_store_path as string | undefined) ?? '',
  }
}

export async function promoteSessionAttachmentToKnowledgeBase(
  sessionId: string,
  attachmentId: string,
  vectorStorePath?: string,
  workspaceId?: string,
): Promise<TaskRecord> {
  const searchParams = new URLSearchParams()
  if (vectorStorePath?.trim()) searchParams.set('vector_store_path', vectorStorePath.trim())
  if (workspaceId?.trim()) searchParams.set('workspace_id', workspaceId.trim())
  const query = searchParams.toString() ? `?${searchParams.toString()}` : ''
  const res = await fetch(
    `${BASE}/sessions/${encodeURIComponent(sessionId)}/attachments/${encodeURIComponent(attachmentId)}/promote${query}`,
    { method: 'POST' },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json() as Promise<TaskRecord>
}

export async function clearSessionMessages(sessionId: string): Promise<void> {
  await fetch(`${BASE}/sessions/${sessionId}/messages`, { method: 'DELETE' })
}

export async function promotePanelAnswer(
  sessionId: string,
  answerGroupId: string,
  panelId: string,
): Promise<PromoteAnswerResponse> {
  const res = await fetch(
    `${BASE}/sessions/${encodeURIComponent(sessionId)}/answer-groups/${encodeURIComponent(answerGroupId)}/promote?panel_id=${encodeURIComponent(panelId)}`,
    { method: 'POST' },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json()
}

export async function getAnswerGroupReview(
  sessionId: string,
  answerGroupId: string,
): Promise<AnswerGroupReviewResponse> {
  const res = await fetch(
    `${BASE}/sessions/${encodeURIComponent(sessionId)}/answer-groups/${encodeURIComponent(answerGroupId)}/review`,
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json() as Promise<AnswerGroupReviewResponse>
}

export async function promoteRecommendedAnswerGroup(
  sessionId: string,
  answerGroupId: string,
): Promise<PromoteAnswerResponse> {
  const res = await fetch(
    `${BASE}/sessions/${encodeURIComponent(sessionId)}/answer-groups/${encodeURIComponent(answerGroupId)}/promote/recommended`,
    { method: 'POST' },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json() as Promise<PromoteAnswerResponse>
}

// 鈹€鈹€ Session Reset 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

export async function resetSession(sessionId: string): Promise<void> {
  await fetch(`${BASE}/sessions/${sessionId}/reset`, { method: 'POST' })
}

export async function createSessionShareLink(sessionId: string): Promise<ShareLinkResponse> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/share`, {
    method: 'POST',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json() as Promise<ShareLinkResponse>
}
