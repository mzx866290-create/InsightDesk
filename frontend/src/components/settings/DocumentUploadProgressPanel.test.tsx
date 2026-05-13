import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { TaskRecord } from '../../api/client'
import { DocumentUploadProgressPanel } from './DocumentUploadProgressPanel'

const task = (status: TaskRecord['status'], progress = 42): TaskRecord => ({
  task_id: 'task-1',
  task_type: 'document_upload',
  status,
  progress,
  created_at: 1,
})

describe('DocumentUploadProgressPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders waiting status when the task record is not available yet', () => {
    render(<DocumentUploadProgressPanel uploadTaskId="task-1" uploadProgress={0} />)

    expect(screen.getByTestId('settings-documents-upload-status')).toHaveTextContent('等待任务状态')
    expect(screen.getByTestId('settings-documents-upload-percent')).toHaveTextContent('0%')
    expect(screen.getByTestId('settings-documents-upload-task-id')).toHaveTextContent('task-1')
  })

  it('renders running, completed, and failed progress states', () => {
    const { rerender } = render(
      <DocumentUploadProgressPanel uploadTaskId="task-1" uploadTask={task('running')} uploadProgress={42} />,
    )

    expect(screen.getByTestId('settings-documents-upload-status')).toHaveTextContent('处理中')
    expect(screen.getByTestId('settings-documents-upload-percent')).toHaveTextContent('42%')

    rerender(<DocumentUploadProgressPanel uploadTaskId="task-1" uploadTask={task('completed', 100)} uploadProgress={100} />)
    expect(screen.getByTestId('settings-documents-upload-status')).toHaveTextContent('已完成')
    expect(screen.getByTestId('settings-documents-upload-percent')).toHaveTextContent('100%')

    rerender(<DocumentUploadProgressPanel uploadTaskId="task-1" uploadTask={task('failed', 15)} uploadProgress={15} />)
    expect(screen.getByTestId('settings-documents-upload-status')).toHaveTextContent('失败')
    expect(screen.getByTestId('settings-documents-upload-percent')).toHaveTextContent('15%')
  })
})
