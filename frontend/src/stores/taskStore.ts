import { create } from 'zustand'

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface TaskRecord {
  task_id: string
  task_type: string
  status: TaskStatus
  progress: number
  result?: string
  error?: string
  created_at: number
  updated_at: number
  params?: Record<string, unknown>
}

interface TaskState {
  tasks: Record<string, TaskRecord>
  // Track active polling timers: task_id → interval handle
  _pollingTimers: Record<string, ReturnType<typeof setInterval>>

  // Actions
  addTask: (task: TaskRecord) => void
  updateTask: (taskId: string, patch: Partial<TaskRecord>) => void
  startPolling: (taskId: string) => void
  stopPolling: (taskId: string) => void
  getTask: (taskId: string) => TaskRecord | undefined
}

const POLL_INTERVAL_MS = 1500

export const useTaskStore = create<TaskState>((set, get) => ({
  tasks: {},
  _pollingTimers: {},

  addTask: (task) =>
    set((s) => ({ tasks: { ...s.tasks, [task.task_id]: task } })),

  updateTask: (taskId, patch) =>
    set((s) => {
      const existing = s.tasks[taskId]
      if (!existing) return s
      return { tasks: { ...s.tasks, [taskId]: { ...existing, ...patch } } }
    }),

  getTask: (taskId) => get().tasks[taskId],

  startPolling: (taskId) => {
    const { _pollingTimers, stopPolling } = get()

    // Avoid duplicate timers
    if (_pollingTimers[taskId]) return

    const timer = setInterval(async () => {
      try {
        const res = await fetch(`/api/tasks/${taskId}`)
        if (!res.ok) {
          stopPolling(taskId)
          return
        }
        const data: TaskRecord = await res.json()
        get().updateTask(taskId, data)

        // Stop polling when terminal state reached
        if (data.status === 'completed' || data.status === 'failed') {
          stopPolling(taskId)
        }
      } catch {
        // Network error — keep polling for a few more cycles
      }
    }, POLL_INTERVAL_MS)

    set((s) => ({
      _pollingTimers: { ...s._pollingTimers, [taskId]: timer },
    }))
  },

  stopPolling: (taskId) => {
    const timer = get()._pollingTimers[taskId]
    if (timer !== undefined) {
      clearInterval(timer)
      set((s) => {
        const timers = { ...s._pollingTimers }
        delete timers[taskId]
        return { _pollingTimers: timers }
      })
    }
  },
}))

/**
 * Create a task on the backend and immediately start polling.
 * Returns the initial TaskRecord.
 */
export async function createAndTrackTask(
  taskType: string,
  params: Record<string, unknown> = {},
  sessionId?: string,
): Promise<TaskRecord> {
  const res = await fetch('/api/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_type: taskType, params, session_id: sessionId }),
  })

  if (!res.ok) {
    throw new Error(`Failed to create task: HTTP ${res.status}`)
  }

  const task: TaskRecord = await res.json()
  const store = useTaskStore.getState()
  store.addTask(task)
  store.startPolling(task.task_id)
  return task
}
