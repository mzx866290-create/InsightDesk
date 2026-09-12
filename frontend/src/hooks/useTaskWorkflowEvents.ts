import { useEffect, useRef, useState } from 'react'

import {
  streamTaskWorkflowEvents,
  type WorkflowStepEvent,
} from '../api/workflowEvents'

/**
 * Subscribe to the step-level SSE stream of a workflow task and keep the
 * latest event. Pass a null taskId to stay idle (e.g. when no workflow task
 * is running). The last event survives task switches until a new stream
 * produces one.
 */
export function useTaskWorkflowEvents(taskId: string | null | undefined): {
  lastEvent: WorkflowStepEvent | null
  connected: boolean
} {
  const [lastEvent, setLastEvent] = useState<WorkflowStepEvent | null>(null)
  const [connected, setConnected] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!taskId) {
      setConnected(false)
      return
    }

    const controller = new AbortController()
    setConnected(true)
    streamTaskWorkflowEvents(taskId, (event) => setLastEvent(event), controller.signal)
      .catch(() => {
        // the stream already surfaces events as they arrive; a broken
        // connection falls back to the existing task polling
      })
      .finally(() => {
        if (!controller.signal.aborted) setConnected(false)
      })

    return () => {
      controller.abort()
      setConnected(false)
    }
  }, [taskId])

  return { lastEvent, connected }
}
