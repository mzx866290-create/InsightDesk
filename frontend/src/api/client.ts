const BASE = '/api'

export interface Session {
  session_id: string
  title: string
  created_at: number
  updated_at: number
  message_count: number
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  images?: ChatImage[]
  files?: ChatFile[]
}

export interface ModelConfig {
  panel_id: string
  provider: 'local' | 'cloud'
  model: string
  base_url: string
  api_key: string
  temperature: number
  agent_mode: 'auto' | 'langgraph' | 'function_calling'
}

export interface SourceItem {
  type: 'doc' | 'web'
  title: string
  url?: string
  snippet: string
  index?: number
}

export interface ChatImage {
  name: string
  media_type: string
  data_url: string
}

export interface ChatFile {
  name: string
  media_type: string
  data_url: string
  size_bytes: number
}

export interface SSEChunk {
  panel_id: string
  type: 'chunk' | 'done' | 'error' | 'sources' | 'all_done' | 'task_created'
  content?: string
  error_code?: string
  suggestion?: string
  sources?: SourceItem[]
  task_id?: string
  task_type?: string
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

export interface RetrievalTestResult {
  results_count: number
  latency_ms: number
  top_results?: { source: string; snippet: string }[]
  error?: string
}

export interface MessagesResponse {
  messages: Message[]
  context_limit: number
  total_messages: number
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

export interface DeckBlock {
  id: string
  kind: string
  role: string
  content: {
    text?: string
    items?: string[]
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

export async function getSessions(): Promise<Session[]> {
  const res = await fetch(`${BASE}/sessions`)
  const data = await res.json()
  return data.sessions as Session[]
}

export async function createSession(title = ''): Promise<{ session_id: string; title: string }> {
  const res = await fetch(`${BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
  return res.json()
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`${BASE}/sessions/${sessionId}`, { method: 'DELETE' })
}

export async function getSessionMessages(sessionId: string): Promise<MessagesResponse> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/messages`)
  const data = await res.json()
  return {
    messages: data.messages as Message[],
    context_limit: data.context_limit ?? 16,
    total_messages: data.total_messages ?? (data.messages as Message[]).length,
  }
}

export async function clearSessionMessages(sessionId: string): Promise<void> {
  await fetch(`${BASE}/sessions/${sessionId}/messages`, { method: 'DELETE' })
}

// ── Chat ─────────────────────────────────────

export function streamChat(
  sessionId: string,
  message: string,
  models: ModelConfig[],
  webSearchEnabled: boolean,
  knowledgeBaseEnabled: boolean,
  images: ChatImage[],
  files: ChatFile[],
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
          `HTTP ${res.status}`
        throw new Error(errorMessage)
      }

      if (!res.body) {
        throw new Error('Backend returned an empty response body.')
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

export async function getDocStats(): Promise<DocStats> {
  const res = await fetch(`${BASE}/documents/stats`)
  if (!res.ok) throw new Error('Failed to get stats')
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
  if (!res.ok) throw new Error('Failed to create prompt')
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
  if (!res.ok) throw new Error('Failed to update prompt')
  return res.json()
}

export async function deleteSystemPrompt(id: string): Promise<void> {
  await fetch(`${BASE}/prompts/${id}`, { method: 'DELETE' })
}

export async function activateSystemPrompt(id: string): Promise<{ ok: boolean; kb_status?: string }> {
  const res = await fetch(`${BASE}/prompts/${id}/activate`, { method: 'POST' })
  if (!res.ok) throw new Error('Failed to activate prompt')
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
  if (!res.ok) throw new Error('Failed to create prompt')
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
  if (!res.ok) throw new Error('Failed to update prompt')
  return res.json()
}

// ── Session Reset ─────────────────────────────

export async function resetSession(sessionId: string): Promise<void> {
  await fetch(`${BASE}/sessions/${sessionId}/reset`, { method: 'POST' })
}

// ── Reports ──────────────────────────────────

export async function createDeckDraft(payload: {
  session_id: string
  panel_config: ModelConfig
  knowledge_base_enabled: boolean
  target_slide_count: number
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

// ── Knowledge Bases ───────────────────────────

export async function getKnowledgeBases(): Promise<KnowledgeBase[]> {
  const res = await fetch(`${BASE}/knowledge-bases`)
  const data = await res.json()
  return data.knowledge_bases as KnowledgeBase[]
}

export async function getKBHealth(): Promise<KBHealthData> {
  const res = await fetch(`${BASE}/knowledge-base/health`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to get KB health' }))
    throw new Error(err.detail ?? 'Failed to get KB health')
  }
  return res.json()
}

export async function testKBRetrieval(query: string): Promise<RetrievalTestResult> {
  const res = await fetch(`${BASE}/knowledge-base/test-retrieval`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })
  if (!res.ok) throw new Error('Test retrieval failed')
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
