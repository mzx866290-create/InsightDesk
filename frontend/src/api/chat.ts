import { BASE, fetchWithApiToken } from './auth'
import type { ChatFile, ChatImage, ModelConfig, SSEChunk } from './client'

type StreamCallbacks = {
  onChunk: (chunk: SSEChunk) => void
  onDone: () => void
  onError: (err: string) => void
}

async function readSSEStream(
  res: Response,
  onChunk: (chunk: SSEChunk) => void,
  onDone: () => void,
): Promise<void> {
  if (!res.body) {
    throw new Error('Backend returned an empty streaming response.')
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
      if (!line.startsWith('data: ')) continue

      try {
        const chunk = JSON.parse(line.slice(6)) as SSEChunk
        if (chunk.type === 'all_done') {
          onDone()
        } else {
          onChunk(chunk)
        }
      } catch {
        // Ignore malformed SSE frames and keep the stream alive.
      }
    }
  }
}

async function readStreamError(res: Response): Promise<string> {
  const errorPayload = await res.json().catch(() => null) as
    | { detail?: string; message?: string; code?: string }
    | null
  return errorPayload?.detail ?? errorPayload?.message ?? `Request failed (HTTP ${res.status}).`
}

function createStreamController(
  path: '/chat/parallel' | '/chat/single',
  body: Record<string, unknown>,
  callbacks: StreamCallbacks,
): AbortController {
  const controller = new AbortController()

  const run = async () => {
    try {
      const res = await fetchWithApiToken(`${BASE}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })

      if (!res.ok) {
        throw new Error(await readStreamError(res))
      }

      await readSSEStream(res, callbacks.onChunk, callbacks.onDone)
    } catch (err: unknown) {
      if ((err as Error).name !== 'AbortError') {
        callbacks.onError((err as Error).message ?? String(err))
      }
    }
  }

  run()
  return controller
}

export function streamChat(
  sessionId: string,
  message: string,
  models: ModelConfig[],
  webSearchEnabled: boolean,
  knowledgeBaseEnabled: boolean,
  enabledMcpServers: string[],
  images: ChatImage[],
  files: ChatFile[],
  answerGroupId: string,
  onChunk: (chunk: SSEChunk) => void,
  onDone: () => void,
  onError: (err: string) => void,
  omitHistory = false,
): AbortController {
  return createStreamController(
    '/chat/parallel',
    {
      session_id: sessionId,
      message,
      images,
      files,
      models,
      web_search_enabled: webSearchEnabled,
      knowledge_base_enabled: knowledgeBaseEnabled,
      enabled_mcp_servers: enabledMcpServers,
      answer_group_id: answerGroupId,
      omit_history: omitHistory,
    },
    { onChunk, onDone, onError },
  )
}

export function streamSingleChat(
  sessionId: string,
  message: string,
  panelConfig: ModelConfig,
  webSearchEnabled: boolean,
  knowledgeBaseEnabled: boolean,
  enabledMcpServers: string[],
  images: ChatImage[],
  files: ChatFile[],
  answerGroupId: string,
  replaceAiHistory: boolean,
  onChunk: (chunk: SSEChunk) => void,
  onDone: () => void,
  onError: (err: string) => void,
  omitHistory = false,
): AbortController {
  return createStreamController(
    '/chat/single',
    {
      session_id: sessionId,
      message,
      images,
      files,
      panel_config: panelConfig,
      web_search_enabled: webSearchEnabled,
      knowledge_base_enabled: knowledgeBaseEnabled,
      enabled_mcp_servers: enabledMcpServers,
      answer_group_id: answerGroupId,
      persist_user_history: false,
      persist_ai_history: true,
      replace_ai_history: replaceAiHistory,
      exclude_ai_answer_group_id: answerGroupId,
      omit_history: omitHistory,
    },
    { onChunk, onDone, onError },
  )
}
