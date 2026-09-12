import { beforeEach, describe, expect, it, vi } from 'vitest'

import { cancelTask as cancelTaskRequest } from '../api/client'
import type { TaskCancellationResponse, TaskRecord } from '../api/client'
import { useTaskStore } from './taskStore'

vi.mock('../api/client', () => ({
  cancelTask: vi.fn(),
  createMultiAgentWorkflowTask: vi.fn(),
  getTask: vi.fn(),
  listTasks: vi.fn(),
}))

const mockedCancelTask = vi.mocked(cancelTaskRequest)

function task(status: TaskRecord['status'] = 'running'): TaskRecord {
  return {
    task_id: 'task-1',
    task_type: 'web_research',
    status,
    progress: 25,
    params: {},
    created_at: 1,
    updated_at: 2,
  }
}

describe('taskStore cancellation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useTaskStore.setState({ tasks: {} })
  })

  it('replaces an active task with the cancelled terminal payload', async () => {
    const cancelledTask = {
      ...task('failed'),
      error: 'Task was cancelled by user.',
      params: { task_failure_kind: 'cancelled' },
    }
    const response: TaskCancellationResponse = {
      ok: true,
      cancel_requested: true,
      cancelled: true,
      backend: 'arq',
      external: { requested: true, aborted: true },
      task: cancelledTask,
    }
    mockedCancelTask.mockResolvedValue(response)
    useTaskStore.getState().addTask(task())

    const result = await useTaskStore.getState().cancelTask('task-1')

    expect(result).toEqual(response)
    expect(mockedCancelTask).toHaveBeenCalledWith('task-1')
    expect(useTaskStore.getState().tasks['task-1']).toEqual(cancelledTask)
  })
})
