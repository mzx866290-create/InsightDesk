import { create } from 'zustand'

import { fetchWithApiToken } from '../api/auth'
import { createMultiAgentWorkflowTask, getTask, listTasks } from '../api/client'
import type {
  CreateMultiAgentWorkflowTaskPayload,
  TaskRecord,
  TaskStatus,
} from '../api/client'

interface TaskState {
  tasks: Record<string, TaskRecord>
  addTask: (task: TaskRecord) => void
  addTasks: (tasks: TaskRecord[]) => void
  updateTask: (taskId: string, patch: Partial<TaskRecord>) => void
  startPolling: (taskId: string) => void
  stopPolling: (taskId: string) => void
  getTask: (taskId: string) => TaskRecord | undefined
  syncRecentTasks: (limit?: number, status?: TaskStatus) => Promise<void>
}

const POLL_INTERVAL_MS = 1500
const HIDDEN_POLL_INTERVAL_MS = 5000
const FAILURE_BACKOFF_MS = 12000

const _activeTaskIds = new Set<string>()
let _pollTimer: ReturnType<typeof setTimeout> | null = null
let _pollInFlight = false
let _consecutivePollFailures = 0

function isActiveTaskStatus(status: string | undefined): boolean {
  return status === 'pending' || status === 'running'
}

function clearPollTimer(): void {
  if (_pollTimer !== null) {
    clearTimeout(_pollTimer)
    _pollTimer = null
  }
}

function resolvePollIntervalMs(): number {
  const visibilityState =
    typeof document !== 'undefined' && typeof document.visibilityState === 'string'
      ? document.visibilityState
      : 'visible'
  const baseInterval = visibilityState === 'hidden' ? HIDDEN_POLL_INTERVAL_MS : POLL_INTERVAL_MS
  if (_consecutivePollFailures <= 0) return baseInterval
  return Math.max(baseInterval, FAILURE_BACKOFF_MS)
}

function schedulePoll(delayMs = resolvePollIntervalMs()): void {
  clearPollTimer()
  if (_activeTaskIds.size === 0) return
  _pollTimer = setTimeout(() => {
    void pollTrackedTasks()
  }, Math.max(0, delayMs))
}

async function pollTrackedTasks(): Promise<void> {
  if (_pollInFlight) return

  const taskIds = [..._activeTaskIds]
  if (taskIds.length === 0) {
    clearPollTimer()
    return
  }

  _pollInFlight = true
  try {
    const results = await Promise.allSettled(taskIds.map((taskId) => getTask(taskId)))
    let successCount = 0

    results.forEach((result, index) => {
      const taskId = taskIds[index]
      if (result.status !== 'fulfilled') return

      successCount += 1
      const task = result.value
      useTaskStore.getState().updateTask(taskId, task)
      if (isActiveTaskStatus(task.status)) {
        _activeTaskIds.add(taskId)
      } else {
        _activeTaskIds.delete(taskId)
      }
    })

    _consecutivePollFailures = successCount > 0 ? 0 : _consecutivePollFailures + 1
  } catch {
    _consecutivePollFailures += 1
  } finally {
    _pollInFlight = false
    if (_activeTaskIds.size === 0) {
      clearPollTimer()
    } else {
      schedulePoll()
    }
  }
}

export const useTaskStore = create<TaskState>((set, get) => ({
  tasks: {},

  addTask: (task) =>
    set((state) => ({ tasks: { ...state.tasks, [task.task_id]: task } })),

  addTasks: (tasks) =>
    set((state) => ({
      tasks: {
        ...state.tasks,
        ...Object.fromEntries(tasks.map((task) => [task.task_id, task])),
      },
    })),

  updateTask: (taskId, patch) =>
    set((state) => {
      const existing = state.tasks[taskId]
      if (!existing) return state
      return {
        tasks: {
          ...state.tasks,
          [taskId]: { ...existing, ...patch },
        },
      }
    }),

  getTask: (taskId) => get().tasks[taskId],

  startPolling: (taskId) => {
    const task = get().tasks[taskId]
    if (task && !isActiveTaskStatus(task.status)) {
      _activeTaskIds.delete(taskId)
      if (_activeTaskIds.size === 0) clearPollTimer()
      return
    }

    _activeTaskIds.add(taskId)
    schedulePoll(0)
  },

  stopPolling: (taskId) => {
    _activeTaskIds.delete(taskId)
    if (_activeTaskIds.size === 0) {
      clearPollTimer()
    }
  },

  syncRecentTasks: async (limit = 20, status) => {
    const tasks = await listTasks(limit, status)
    get().addTasks(tasks)
    for (const task of tasks) {
      if (isActiveTaskStatus(task.status)) {
        get().startPolling(task.task_id)
      } else {
        get().stopPolling(task.task_id)
      }
    }
  },
}))

export async function createAndTrackTask(
  taskType: string,
  params: Record<string, unknown> = {},
  sessionId?: string,
): Promise<TaskRecord> {
  const normalizedParams = { ...params }
  if (taskType === 'web_research') {
    const providers = Array.isArray(normalizedParams.providers)
      ? normalizedParams.providers
          .map((item) => String(item).trim().toLowerCase())
          .filter(Boolean)
      : null

    // Let the backend choose the default provider sequence unless the caller
    // explicitly requests a non-default search stack.
    if (!providers?.length || (providers.length === 1 && providers[0] === 'tavily')) {
      delete normalizedParams.providers
    } else {
      normalizedParams.providers = providers
    }
  }

  const res = await fetchWithApiToken('/api/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_type: taskType, params: normalizedParams, session_id: sessionId }),
  })

  if (!res.ok) {
    const payload = await res
      .json()
      .catch(() => null) as { detail?: string; message?: string } | null
    const detail =
      payload?.detail?.trim() || payload?.message?.trim() || `Task creation failed (HTTP ${res.status})`
    throw new Error(detail)
  }

  const task: TaskRecord = await res.json()
  const store = useTaskStore.getState()
  store.addTask(task)
  store.startPolling(task.task_id)
  return task
}

export async function createAndTrackWorkflowTask(
  payload: CreateMultiAgentWorkflowTaskPayload,
): Promise<TaskRecord> {
  const task = await createMultiAgentWorkflowTask(payload)
  const store = useTaskStore.getState()
  store.addTask(task)
  if (isActiveTaskStatus(task.status)) {
    store.startPolling(task.task_id)
  } else {
    store.stopPolling(task.task_id)
  }
  return task
}
