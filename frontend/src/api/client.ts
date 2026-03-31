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

export interface SystemPrompt {
  id: string
  name: string
  content: string
  is_default: boolean
  is_active: boolean
  created_at: number
  updated_at: number
}

export interface MessagesResponse {
  messages: Message[]
  context_limit: number
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
  return { messages: data.messages as Message[], context_limit: data.context_limit ?? 16 }
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
          models,
          web_search_enabled: webSearchEnabled,
        }),
        signal: controller.signal,
      })

      if (!res.ok || !res.body) {
        throw new Error(`HTTP ${res.status}`)
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

export async function uploadDocuments(files: File[]): Promise<{ count: number; message: string }> {
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

export async function createSystemPrompt(name: string, content: string): Promise<SystemPrompt> {
  const res = await fetch(`${BASE}/prompts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, content }),
  })
  if (!res.ok) throw new Error('Failed to create prompt')
  return res.json()
}

export async function updateSystemPrompt(id: string, name: string, content: string): Promise<SystemPrompt> {
  const res = await fetch(`${BASE}/prompts/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, content }),
  })
  if (!res.ok) throw new Error('Failed to update prompt')
  return res.json()
}

export async function deleteSystemPrompt(id: string): Promise<void> {
  await fetch(`${BASE}/prompts/${id}`, { method: 'DELETE' })
}

export async function activateSystemPrompt(id: string): Promise<void> {
  await fetch(`${BASE}/prompts/${id}/activate`, { method: 'POST' })
}
