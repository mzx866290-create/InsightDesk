import { BASE, fetchWithApiToken } from './auth'

export interface WorkflowStepEvent {
  type: string
  task_id?: string
  step_id?: string
  step_index?: number
  agent?: string
  status?: string
  error?: string
  final_output?: string
  [key: string]: unknown
}

const TERMINAL_EVENT_TYPES = new Set(['workflow_completed', 'workflow_failed'])

export function isTerminalWorkflowEvent(event: WorkflowStepEvent): boolean {
  return TERMINAL_EVENT_TYPES.has(event.type)
}

/**
 * Consume the step-level SSE stream of a workflow task until a terminal
 * event arrives, the caller aborts, or the connection breaks. Mirrors the
 * fetch-based SSE convention used by chat streaming (no EventSource, so the
 * auth headers injected by fetchWithApiToken apply).
 */
export async function streamTaskWorkflowEvents(
  taskId: string,
  onEvent: (event: WorkflowStepEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetchWithApiToken(
    `${BASE}/tasks/${encodeURIComponent(taskId)}/events`,
    { method: 'POST', signal },
  )
  if (!res.ok || !res.body) {
    throw new Error(`Workflow event stream failed with status ${res.status}`)
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
        const event = JSON.parse(line.slice(6)) as WorkflowStepEvent
        onEvent(event)
        if (isTerminalWorkflowEvent(event)) return
      } catch {
        // ignore malformed frames; the backend controls the payload
      }
    }
  }
}
