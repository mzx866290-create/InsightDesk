import type { WorkflowNode } from '../stores/workflowStore'

const BASE = '/api'

export interface Session {
  session_id: string
  title: string
  created_at: number
  updated_at: number
  message_count: number
  is_archived: boolean
  is_favorite: boolean
  is_pinned: boolean
  session_order: number
  tags: string[]
  workspace_id: string
  search_preview?: string
  search_source?: 'title' | 'message'
}

export interface Workspace {
  workspace_id: string
  name: string
  description: string
  color: 'slate' | 'blue' | 'green' | 'amber' | 'rose'
  is_active: boolean
  created_at: number
  updated_at: number
  session_count: number
}

export type SessionMemoryKind = 'summary' | 'fact' | 'decision' | 'todo'
export type MessageFeedbackValue = -1 | 0 | 1
export type RetrievalFeedbackValue = -1 | 0 | 1

export interface SessionMemory {
  id: string
  session_id: string
  kind: SessionMemoryKind
  content: string
  meta?: Record<string, unknown>
  created_at: number
  updated_at: number
}

function normalizeSession(raw: Partial<Session> & Pick<Session, 'session_id' | 'title' | 'created_at' | 'updated_at' | 'message_count'>): Session {
  return {
    session_id: raw.session_id,
    title: raw.title,
    created_at: raw.created_at,
    updated_at: raw.updated_at,
    message_count: raw.message_count,
    is_archived: raw.is_archived === true,
    is_favorite: raw.is_favorite === true,
    is_pinned: raw.is_pinned === true,
    session_order: Number(raw.session_order ?? 0) || 0,
    tags: Array.isArray(raw.tags)
      ? raw.tags.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
      : [],
    workspace_id: typeof raw.workspace_id === 'string' && raw.workspace_id.trim()
      ? raw.workspace_id.trim()
      : 'workspace-default',
    search_preview:
      typeof raw.search_preview === 'string' && raw.search_preview.trim()
        ? raw.search_preview
        : undefined,
    search_source: raw.search_source === 'message' ? 'message' : raw.search_source === 'title' ? 'title' : undefined,
  }
}

function normalizeWorkspace(raw: Partial<Workspace> & Pick<Workspace, 'workspace_id' | 'name' | 'created_at' | 'updated_at' | 'session_count'>): Workspace {
  const color = typeof raw.color === 'string' ? raw.color.trim().toLowerCase() : 'blue'
  return {
    workspace_id: raw.workspace_id,
    name: raw.name,
    description: typeof raw.description === 'string' ? raw.description : '',
    color: (['slate', 'blue', 'green', 'amber', 'rose'].includes(color) ? color : 'blue') as Workspace['color'],
    is_active: raw.is_active === true,
    created_at: raw.created_at,
    updated_at: raw.updated_at,
    session_count: Number(raw.session_count ?? 0),
  }
}

function normalizeBookmark(raw: Partial<Bookmark> & { id: string }): Bookmark {
  const rawBookmark = raw as Partial<Bookmark> & {
    session_id?: string
    session_title?: string
    message_id?: number
    panel_id?: string
    answer_group_id?: string
    model_id?: string
    created_at?: number
    updated_at?: number
  }

  return {
    id: raw.id,
    sessionId:
      typeof rawBookmark.sessionId === 'string' && rawBookmark.sessionId.trim()
        ? rawBookmark.sessionId.trim()
        : typeof rawBookmark.session_id === 'string' && rawBookmark.session_id.trim()
          ? rawBookmark.session_id.trim()
          : '',
    sessionTitle:
      typeof rawBookmark.sessionTitle === 'string'
        ? rawBookmark.sessionTitle
        : typeof rawBookmark.session_title === 'string'
          ? rawBookmark.session_title
          : '',
    messageId:
      typeof rawBookmark.messageId === 'number'
        ? rawBookmark.messageId
        : typeof rawBookmark.message_id === 'number'
          ? rawBookmark.message_id
          : undefined,
    panelId:
      typeof rawBookmark.panelId === 'string'
        ? rawBookmark.panelId
        : typeof rawBookmark.panel_id === 'string'
          ? rawBookmark.panel_id
          : '',
    answerGroupId:
      typeof rawBookmark.answerGroupId === 'string'
        ? rawBookmark.answerGroupId
        : typeof rawBookmark.answer_group_id === 'string'
          ? rawBookmark.answer_group_id
          : '',
    role: rawBookmark.role === 'user' ? 'user' : 'assistant',
    content: typeof rawBookmark.content === 'string' ? rawBookmark.content : '',
    modelId:
      typeof rawBookmark.modelId === 'string'
        ? rawBookmark.modelId
        : typeof rawBookmark.model_id === 'string'
          ? rawBookmark.model_id
          : undefined,
    createdAt:
      typeof rawBookmark.createdAt === 'number'
        ? rawBookmark.createdAt
        : typeof rawBookmark.created_at === 'number'
          ? rawBookmark.created_at
          : Date.now() / 1000,
    updatedAt:
      typeof rawBookmark.updatedAt === 'number'
        ? rawBookmark.updatedAt
        : typeof rawBookmark.updated_at === 'number'
          ? rawBookmark.updated_at
          : Date.now() / 1000,
    source: rawBookmark.source === 'local' ? 'local' : 'remote',
  }
}

export interface Message {
  id?: number
  role: 'user' | 'assistant'
  content: string
  images?: ChatImage[]
  files?: ChatFile[]
  sources?: SourceItem[]
  model_id?: string
  panel_id?: string
  answer_group_id?: string
  workflow_nodes?: WorkflowNode[]
  task_id?: string
  task_type?: string
  timestamp?: number
  feedback_value?: MessageFeedbackValue
}

export interface SessionPanel {
  panel_id: string
  is_primary: boolean
  display_order: number
  model_config: ModelConfig
}

export type ConnectionType = 'ollama' | 'openai_compatible'

export interface ModelConfig {
  panel_id: string
  connection_type?: ConnectionType
  provider?: ConnectionType | 'local' | 'cloud' | 'openai' | 'openrouter'
  model: string
  base_url: string
  api_key: string
  temperature: number
  agent_mode: 'auto' | 'langgraph' | 'function_calling' | 'plain_chat'
}

export function normalizeConnectionType(
  connectionType?: string,
  baseUrl?: string,
): ConnectionType {
  const rawType = (connectionType ?? '').trim().toLowerCase()
  const rawBaseUrl = (baseUrl ?? '').trim().toLowerCase()

  if (rawType === 'ollama' || rawType === 'local') return 'ollama'
  if (
    rawType === 'openai_compatible' ||
    rawType === 'cloud' ||
    rawType === 'openai' ||
    rawType === 'openrouter'
  ) {
    return 'openai_compatible'
  }

  if (rawBaseUrl.includes('11434')) return 'ollama'
  return 'openai_compatible'
}

export function defaultBaseUrlForConnectionType(connectionType: ConnectionType): string {
  return connectionType === 'ollama'
    ? 'http://localhost:11434'
    : 'https://openrouter.ai/api/v1'
}

export function defaultModelForConnectionType(connectionType: ConnectionType): string {
  return connectionType === 'ollama' ? 'qwen3.5-2B:latest' : 'gpt-4o-mini'
}

export function normalizeModelConfig(config: Partial<ModelConfig> & { panel_id: string }): ModelConfig {
  const connectionType = normalizeConnectionType(
    config.connection_type ?? config.provider,
    config.base_url,
  )
  return {
    panel_id: config.panel_id,
    connection_type: connectionType,
    provider: connectionType,
    model: (config.model ?? defaultModelForConnectionType(connectionType)).trim(),
    base_url: (config.base_url ?? defaultBaseUrlForConnectionType(connectionType)).trim(),
    api_key: config.api_key ?? '',
    temperature: config.temperature ?? 0.3,
    agent_mode: config.agent_mode ?? 'auto',
  }
}

export function getConnectionTypeLabel(modelConfig: ModelConfig): string {
  const connectionType = normalizeConnectionType(
    modelConfig.connection_type ?? modelConfig.provider,
    modelConfig.base_url,
  )
  return connectionType === 'ollama' ? '本地 Ollama' : 'OpenAI 兼容'
}

export interface SourceItem {
  type: 'doc' | 'web' | 'attachment'
  title: string
  url?: string
  snippet: string
  index?: number
  answer_group_id?: string
  attachment_kind?: 'file' | 'image'
  media_type?: string
  data_url?: string
}

export interface ChatImage {
  name: string
  media_type: string
  data_url: string
}

export interface ChatFile {
  name: string
  media_type: string
  data_url?: string
  size_bytes: number
  extracted_text?: string
}

export interface SessionAttachment {
  attachment_id: string
  kind: 'file' | 'image'
  name: string
  media_type: string
  data_url?: string
  size_bytes: number
  extracted_text?: string
  preview_text?: string
  text_char_count: number
  occurrence_count: number
  turn_count: number
  first_seen_at: number
  last_seen_at: number
  latest_answer_group_id?: string
  current_vector_store_path?: string
  promotion_status?: 'idle' | TaskStatus
  promotion_task_id?: string | null
  promotion_updated_at?: number | null
  is_in_current_kb?: boolean
}

export interface SessionAttachmentSummary {
  total_attachments: number
  file_count: number
  image_count: number
  text_ready_count: number
  reusable_count: number
  total_size_bytes: number
  indexed_in_current_kb_count?: number
  indexing_in_current_kb_count?: number
}

export interface SSEChunk {
  panel_id: string
  type: 'chunk' | 'done' | 'error' | 'sources' | 'all_done' | 'task_created' | 'workflow_state'
  content?: string
  error_code?: string
  suggestion?: string
  sources?: SourceItem[]
  task_id?: string
  task_type?: string
  node_name?: string
  status?: 'running' | 'completed' | 'failed'
  duration_ms?: number
  tool_name?: string
  tool_params?: Record<string, unknown>
  tool_result_summary?: string
  error?: string
  timestamp?: number
}

export interface DocStats {
  status: string
  total_docs?: number
  store_path?: string
}

export interface UploadDocumentsResponse {
  ok: boolean
  task_id: string
  task_type: string
  status: string
  message: string
}

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface TaskRecord {
  task_id: string
  task_type: string
  status: TaskStatus
  progress: number
  result?: string
  error?: string
  params?: Record<string, unknown>
  session_id?: string | null
  created_at: number
  updated_at?: number
}

export interface SystemPrompt {
  id: string
  name: string
  content: string
  is_default: boolean
  is_active: boolean
  created_at: number
  updated_at: number
  vector_store_id?: string
  dashboard_template?: DashboardTemplateConfig
}

export interface DashboardTemplateConfig {
  enabled: boolean
  title_hint: string
  focus_metrics: string[]
  preferred_charts: Array<'bar' | 'line' | 'pie'>
  section_order: Array<'summary' | 'metrics' | 'charts' | 'table' | 'evidence' | 'warnings'>
  audience_tone: string
}

export interface KnowledgeBase {
  id: string
  name: string
  path: string
  doc_count: number
  has_index: boolean
}

export interface KBHealthData {
  index_status: 'healthy' | 'empty' | 'not_found' | 'error'
  total_chunks: number
  store_path: string
  store_size_mb: number
  documents: { name: string; chunks: number }[]
  embedding_model: string
  last_updated: number | null
}

export interface KnowledgeBaseChunk {
  chunk_id: string
  position: number
  source: string
  content: string
  preview: string
  char_count: number
  metadata: Record<string, unknown>
}

export interface KnowledgeBaseChunksResponse {
  items: KnowledgeBaseChunk[]
  total: number
  offset: number
  limit: number
  has_more: boolean
  store_path: string
}

export interface RetrievalTestResult {
  results_count: number
  latency_ms: number
  search_mode?: 'vector' | 'vector_rerank'
  search_k?: number
  fetch_k?: number
  top_results?: { source: string; snippet: string }[]
  error?: string
}

export interface MessagesResponse {
  messages: Message[]
  context_limit: number
  total_messages: number
  panels?: SessionPanel[]
  panel_messages?: Record<string, Message[]>
}

export interface Bookmark {
  id: string
  sessionId: string
  sessionTitle: string
  messageId?: number
  panelId: string
  answerGroupId: string
  role: 'user' | 'assistant'
  content: string
  modelId?: string
  createdAt: number
  updatedAt: number
  source?: 'remote' | 'local'
}

export interface SessionAttachmentsResponse {
  session_id: string
  attachments: SessionAttachment[]
  summary: SessionAttachmentSummary
  current_vector_store_path?: string
}

export interface ShareLinkResponse {
  resource_type: 'session' | 'deck'
  resource_id: string
  share_token: string
  share_url: string
}

export interface DeckWarning {
  code: string
  message: string
}

export interface DeckMeta {
  title: string
  subtitle: string
  language: string
  audience: string
  purpose: string
  author: string
  theme: 'default' | 'midnight' | 'sunrise'
  created_at: string
  session_id: string
  source_mode: 'kb_plus_chat' | 'chat_only'
  generator_panel_id: string
}

export interface DeckGeneration {
  source: 'kb_plus_chat' | 'chat_only'
  target_slide_count: number
  actual_slide_count: number
  warnings: DeckWarning[]
}

export interface DeckChartDataset {
  label: string
  data: number[]
}

export interface DeckBlock {
  id: string
  kind: string
  role: string
  content: {
    text?: string
    items?: string[]
    title?: string
    description?: string
    chart_type?: 'bar' | 'line' | 'pie'
    labels?: string[]
    datasets?: DeckChartDataset[]
  }
  editable: boolean
}

export interface DeckEvidenceRef {
  id: string
  source_id: string
  source_title: string
  excerpt_id?: string | null
  snippet: string
  confidence: number
}

export interface DeckSlideStatus {
  locked: boolean
  dirty: boolean
  review_state: string
}

export interface DeckSlide {
  id: string
  type: string
  title: string
  subtitle: string
  layout: string
  intent: string
  speaker_notes: string
  blocks: DeckBlock[]
  evidence_refs: DeckEvidenceRef[]
  quality_state: 'supported' | 'weak_support' | 'manual'
  status: DeckSlideStatus
}

export interface DeckSourceItem {
  id: string
  type: string
  title: string
  document_id?: string | null
  uri?: string | null
  metadata: Record<string, unknown>
}

export interface DeckSpec {
  version: string
  deck_id: string
  status: string
  meta: DeckMeta
  generation: DeckGeneration
  slides: DeckSlide[]
  source_registry: DeckSourceItem[]
}

// ── Sessions ─────────────────────────────────

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
}): Promise<Workspace> {
  const res = await fetch(`${BASE}/workspaces`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: payload.name,
      description: payload.description ?? '',
      color: payload.color ?? 'blue',
      activate: payload.activate ?? true,
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
  },
): Promise<Workspace> {
  const res = await fetch(`${BASE}/workspaces/${encodeURIComponent(workspaceId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
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
    throw new Error('删除工作区返回的数据无效。')
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
    throw new Error('创建会话返回的数据无效。')
  }
  return {
    session_id: data.session_id,
    title: typeof data.title === 'string' && data.title.trim() ? data.title : '新建对话',
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
    throw new Error('创建书签返回的数据无效。')
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
    throw new Error('至少需要两个对话才能重新排序。')
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
    throw new Error('消息反馈返回的数据无效。')
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
    throw new Error('截断请求返回的数据无效。')
  }
  return data.result
}

const normalizeRetrievalSourceText = (value: unknown): string =>
  String(value ?? '')
    .trim()
    .replace(/\s+/g, ' ')

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
    throw new Error('检索反馈返回的数据无效。')
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
): Promise<SessionAttachmentsResponse> {
  const query = vectorStorePath?.trim()
    ? `?vector_store_path=${encodeURIComponent(vectorStorePath.trim())}`
    : ''
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
): Promise<TaskRecord> {
  const query = vectorStorePath?.trim()
    ? `?vector_store_path=${encodeURIComponent(vectorStorePath.trim())}`
    : ''
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
): Promise<{
  ok: boolean
  target_panel_id: string
  source_panel_id: string
  answer_group_id: string
  content: string
  model_id: string
}> {
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

// ── Chat ─────────────────────────────────────

async function readSSEStream(
  res: Response,
  onChunk: (chunk: SSEChunk) => void,
  onDone: () => void,
): Promise<void> {
  if (!res.body) {
    throw new Error('后端返回了空响应。')
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const chunk = JSON.parse(line.slice(6)) as SSEChunk
          if (chunk.type === 'all_done') {
            onDone()
          } else {
            onChunk(chunk)
          }
        } catch {
          // skip malformed
        }
      }
    }
  }
}

export function streamChat(
  sessionId: string,
  message: string,
  models: ModelConfig[],
  webSearchEnabled: boolean,
  knowledgeBaseEnabled: boolean,
  images: ChatImage[],
  files: ChatFile[],
  answerGroupId: string,
  onChunk: (chunk: SSEChunk) => void,
  onDone: () => void,
  onError: (err: string) => void,
): AbortController {
  const controller = new AbortController()

  const run = async () => {
    try {
      const res = await fetch(`${BASE}/chat/parallel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message,
          images,
          files,
          models,
          web_search_enabled: webSearchEnabled,
          knowledge_base_enabled: knowledgeBaseEnabled,
          answer_group_id: answerGroupId,
        }),
        signal: controller.signal,
      })

      if (!res.ok) {
        const errorPayload = await res.json().catch(() => null) as
          | { detail?: string; message?: string; code?: string }
          | null
        const errorMessage =
          errorPayload?.detail ??
          errorPayload?.message ??
          `请求失败（HTTP ${res.status}）`
        throw new Error(errorMessage)
      }

      await readSSEStream(res, onChunk, onDone)
    } catch (err: unknown) {
      if ((err as Error).name !== 'AbortError') {
        onError((err as Error).message ?? String(err))
      }
    }
  }

  run()
  return controller
}

export function streamSingleChat(
  sessionId: string,
  message: string,
  panelConfig: ModelConfig,
  webSearchEnabled: boolean,
  knowledgeBaseEnabled: boolean,
  images: ChatImage[],
  files: ChatFile[],
  answerGroupId: string,
  replaceAiHistory: boolean,
  onChunk: (chunk: SSEChunk) => void,
  onDone: () => void,
  onError: (err: string) => void,
): AbortController {
  const controller = new AbortController()

  const run = async () => {
    try {
      const res = await fetch(`${BASE}/chat/single`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message,
          images,
          files,
          panel_config: panelConfig,
          web_search_enabled: webSearchEnabled,
          knowledge_base_enabled: knowledgeBaseEnabled,
          answer_group_id: answerGroupId,
          persist_user_history: false,
          persist_ai_history: true,
          replace_ai_history: replaceAiHistory,
          exclude_ai_answer_group_id: answerGroupId,
        }),
        signal: controller.signal,
      })

      if (!res.ok) {
        const errorPayload = await res.json().catch(() => null) as
          | { detail?: string; message?: string; code?: string }
          | null
        const errorMessage =
          errorPayload?.detail ??
          errorPayload?.message ??
          `请求失败（HTTP ${res.status}）`
        throw new Error(errorMessage)
      }

      await readSSEStream(res, onChunk, onDone)
    } catch (err: unknown) {
      if ((err as Error).name !== 'AbortError') {
        onError((err as Error).message ?? String(err))
      }
    }
  }

  run()
  return controller
}

// ── Models ───────────────────────────────────

export async function getOllamaModels(baseUrl = 'http://localhost:11434'): Promise<string[]> {
  try {
    const res = await fetch(`${BASE}/models/ollama?base_url=${encodeURIComponent(baseUrl)}`)
    const data = await res.json()
    return (data.models as string[]) ?? []
  } catch {
    return []
  }
}

// ── Config ───────────────────────────────────

export async function getConfig() {
  const res = await fetch(`${BASE}/config`)
  return res.json()
}

export async function saveConfig(payload: { tavily_api_key?: string }): Promise<void> {
  await fetch(`${BASE}/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function resetAgents(): Promise<void> {
  await fetch(`${BASE}/agents/reset`, { method: 'POST' })
}

// ── Documents ────────────────────────────────

export async function uploadDocuments(files: File[]): Promise<UploadDocumentsResponse> {
  const form = new FormData()
  for (const f of files) form.append('files', f)
  const res = await fetch(`${BASE}/documents/upload`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json()
}

export async function getTask(taskId: string): Promise<TaskRecord> {
  const res = await fetch(`${BASE}/tasks/${taskId}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json()
}

export async function listTasks(limit = 20): Promise<TaskRecord[]> {
  const res = await fetch(`${BASE}/tasks?limit=${encodeURIComponent(String(limit))}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as { tasks?: TaskRecord[] }
  return data.tasks ?? []
}

export async function getDocStats(): Promise<DocStats> {
  const res = await fetch(`${BASE}/documents/stats`)
  if (!res.ok) throw new Error('获取统计信息失败。')
  return res.json()
}

// ── System Prompts ────────────────────────────

export async function getSystemPrompts(): Promise<SystemPrompt[]> {
  const res = await fetch(`${BASE}/prompts`)
  const data = await res.json()
  return data.prompts as SystemPrompt[]
}

export async function createSystemPrompt(
  name: string,
  content: string,
  dashboard_template?: DashboardTemplateConfig,
): Promise<SystemPrompt> {
  const res = await fetch(`${BASE}/prompts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, content, dashboard_template: dashboard_template ?? {} }),
  })
  if (!res.ok) throw new Error('创建角色失败。')
  return res.json()
}

export async function updateSystemPrompt(
  id: string,
  name: string,
  content: string,
  dashboard_template?: DashboardTemplateConfig,
): Promise<SystemPrompt> {
  const res = await fetch(`${BASE}/prompts/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, content, dashboard_template: dashboard_template ?? {} }),
  })
  if (!res.ok) throw new Error('更新角色失败。')
  return res.json()
}

export async function deleteSystemPrompt(id: string): Promise<void> {
  await fetch(`${BASE}/prompts/${id}`, { method: 'DELETE' })
}

export async function activateSystemPrompt(id: string): Promise<{ ok: boolean; kb_status?: string }> {
  const res = await fetch(`${BASE}/prompts/${id}/activate`, { method: 'POST' })
  if (!res.ok) throw new Error('启用角色失败。')
  return res.json()
}

export async function createSystemPromptWithKB(
  name: string,
  content: string,
  vectorStoreId?: string,
  dashboardTemplate?: DashboardTemplateConfig,
): Promise<SystemPrompt> {
  const res = await fetch(`${BASE}/prompts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      content,
      vector_store_id: vectorStoreId ?? '',
      dashboard_template: dashboardTemplate ?? {},
    }),
  })
  if (!res.ok) throw new Error('创建角色失败。')
  return res.json()
}

export async function updateSystemPromptWithKB(
  id: string,
  name: string,
  content: string,
  vectorStoreId?: string,
  dashboardTemplate?: DashboardTemplateConfig,
): Promise<SystemPrompt> {
  const res = await fetch(`${BASE}/prompts/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      content,
      vector_store_id: vectorStoreId ?? '',
      dashboard_template: dashboardTemplate ?? {},
    }),
  })
  if (!res.ok) throw new Error('更新角色失败。')
  return res.json()
}

// ── Session Reset ─────────────────────────────

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

// ── Reports ──────────────────────────────────

export async function createDeckDraft(payload: {
  session_id: string
  panel_config: ModelConfig
  knowledge_base_enabled: boolean
  target_slide_count: number
  theme?: 'default' | 'midnight' | 'sunrise'
}): Promise<DeckSpec> {
  const res = await fetch(`${BASE}/decks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json() as Promise<DeckSpec>
}

export async function getDeck(deckId: string): Promise<DeckSpec> {
  const res = await fetch(`${BASE}/decks/${deckId}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json() as Promise<DeckSpec>
}

export async function updateDeck(deckId: string, payload: {
  title?: string
  theme?: 'default' | 'midnight' | 'sunrise'
  slides?: DeckSlide[]
}): Promise<DeckSpec> {
  const res = await fetch(`${BASE}/decks/${deckId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json() as Promise<DeckSpec>
}

export async function exportDeck(deckId: string, format: 'pptx' = 'pptx'): Promise<Blob> {
  const res = await fetch(`${BASE}/decks/${deckId}/export?format=${format}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.blob()
}

export async function createDeckShareLink(deckId: string): Promise<ShareLinkResponse> {
  const res = await fetch(`${BASE}/decks/${deckId}/share`, {
    method: 'POST',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json() as Promise<ShareLinkResponse>
}

export async function regenerateDeckSlide(
  deckId: string,
  slideId: string,
  payload: {
    panel_config: ModelConfig
    knowledge_base_enabled?: boolean
  },
): Promise<DeckSpec> {
  const res = await fetch(`${BASE}/decks/${deckId}/slides/${slideId}/regenerate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json() as Promise<DeckSpec>
}

// ── Knowledge Bases ───────────────────────────

export async function getKnowledgeBases(): Promise<KnowledgeBase[]> {
  const res = await fetch(`${BASE}/knowledge-bases`)
  const data = await res.json()
  return data.knowledge_bases as KnowledgeBase[]
}

export async function getKBHealth(): Promise<KBHealthData> {
  const res = await fetch(`${BASE}/knowledge-base/health`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '获取知识库健康状态失败。' }))
    throw new Error(err.detail ?? '获取知识库健康状态失败。')
  }
  return res.json()
}

export async function getKnowledgeBaseChunks(params?: {
  path?: string
  query?: string
  source?: string
  offset?: number
  limit?: number
}): Promise<KnowledgeBaseChunksResponse> {
  const searchParams = new URLSearchParams()
  if (params?.path?.trim()) searchParams.set('path', params.path.trim())
  if (params?.query?.trim()) searchParams.set('query', params.query.trim())
  if (params?.source?.trim()) searchParams.set('source', params.source.trim())
  if (typeof params?.offset === 'number' && Number.isFinite(params.offset)) {
    searchParams.set('offset', String(Math.max(0, Math.floor(params.offset))))
  }
  if (typeof params?.limit === 'number' && Number.isFinite(params.limit)) {
    const safeLimit = Math.max(1, Math.min(200, Math.floor(params.limit)))
    searchParams.set('limit', String(safeLimit))
  }

  const query = searchParams.toString()
  const res = await fetch(`${BASE}/knowledge-base/chunks${query ? `?${query}` : ''}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json()
}

export async function updateKnowledgeBaseChunk(
  chunkId: string,
  payload: {
    content?: string
    source?: string
    path?: string
  },
): Promise<{ ok: boolean; chunk_id: string; reindexed: boolean }> {
  const searchParams = new URLSearchParams()
  if (payload.path?.trim()) searchParams.set('path', payload.path.trim())
  const query = searchParams.toString()
  const res = await fetch(
    `${BASE}/knowledge-base/chunks/${encodeURIComponent(chunkId)}${query ? `?${query}` : ''}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...(payload.content !== undefined ? { content: payload.content } : {}),
        ...(payload.source !== undefined ? { source: payload.source } : {}),
      }),
    },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json()
}

export async function deleteKnowledgeBaseChunk(chunkId: string, path?: string): Promise<void> {
  const searchParams = new URLSearchParams()
  if (path?.trim()) searchParams.set('path', path.trim())
  const query = searchParams.toString()
  const res = await fetch(
    `${BASE}/knowledge-base/chunks/${encodeURIComponent(chunkId)}${query ? `?${query}` : ''}`,
    { method: 'DELETE' },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
}

export async function testKBRetrieval(
  query: string,
  options?: { search_k?: number; fetch_k?: number; use_rerank?: boolean },
): Promise<RetrievalTestResult> {
  const res = await fetch(`${BASE}/knowledge-base/test-retrieval`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, ...options }),
  })
  if (!res.ok) throw new Error('检索测试失败。')
  return res.json()
}

export async function deleteKnowledgeBase(path?: string): Promise<void> {
  const url = path
    ? `${BASE}/knowledge-base/by-path?path=${encodeURIComponent(path)}`
    : `${BASE}/knowledge-base`
  const res = await fetch(url, { method: 'DELETE' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
}
