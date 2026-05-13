import React from 'react'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { getDocStats, uploadDocuments } from '../../api/client'
import type { TaskRecord } from '../../api/client'
import { useTaskStore } from '../../stores/taskStore'
import { DocumentIngestionPanel } from './DocumentIngestionPanel'

vi.mock('../../api/client', () => ({
  getDocStats: vi.fn(),
  uploadDocuments: vi.fn(),
}))

vi.mock('../../stores/taskStore', () => ({
  useTaskStore: vi.fn(),
}))

vi.mock('../ui/Button', () => ({
  Button: ({
    children,
    loading,
    variant: _variant,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    loading?: boolean
    variant?: string
  }) => (
    <button disabled={props.disabled || loading} {...props}>
      {children}
    </button>
  ),
}))

const addTask = vi.fn()
const startPolling = vi.fn()
let tasks: Record<string, TaskRecord>

function mockTaskStore(): void {
  vi.mocked(useTaskStore).mockImplementation((selector) => selector({
    tasks,
    addTask,
    addTasks: vi.fn(),
    updateTask: vi.fn(),
    startPolling,
    stopPolling: vi.fn(),
    getTask: vi.fn(),
    syncRecentTasks: vi.fn(),
  }))
}

const file = (name: string): File => new File(['content'], name, { type: 'text/plain' })

describe('DocumentIngestionPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    tasks = {}
    mockTaskStore()
    vi.mocked(uploadDocuments).mockResolvedValue({
      ok: true,
      task_id: 'upload-task-1',
      task_type: 'document_upload',
      status: 'pending',
      message: 'queued',
    })
    vi.mocked(getDocStats).mockResolvedValue({
      status: 'ready',
      total_docs: 3,
      store_path: '/data/docs',
    })
  })

  afterEach(() => {
    cleanup()
  })

  it('uploads selected files, tracks the task, and renders the upload result', async () => {
    render(
      <DocumentIngestionPanel
        deletingKnowledgeBase={false}
        deleteKnowledgeBaseConfirming={false}
        onDeleteKnowledgeBase={vi.fn()}
      />,
    )

    await act(async () => {
      fireEvent.change(screen.getByTestId('settings-documents-upload-input'), {
        target: {
          files: [file('intro.md')],
        },
      })
    })

    expect(uploadDocuments).toHaveBeenCalledTimes(1)
    expect(vi.mocked(uploadDocuments).mock.calls[0][0].map((selectedFile) => selectedFile.name)).toEqual(['intro.md'])
    expect(addTask).toHaveBeenCalledWith(expect.objectContaining({
      task_id: 'upload-task-1',
      task_type: 'document_upload',
      status: 'pending',
      progress: 0,
    }))
    expect(startPolling).toHaveBeenCalledWith('upload-task-1')
    expect(screen.getByTestId('settings-documents-upload-result')).toHaveAttribute('data-status', 'success')
    expect(screen.getByTestId('settings-documents-upload-result')).toHaveTextContent('queued')
    expect(screen.getByTestId('settings-documents-upload-progress')).toBeInTheDocument()
  })

  it('renders upload errors', async () => {
    vi.mocked(uploadDocuments).mockRejectedValueOnce(new Error('upload failed'))

    render(
      <DocumentIngestionPanel
        deletingKnowledgeBase={false}
        deleteKnowledgeBaseConfirming={false}
        onDeleteKnowledgeBase={vi.fn()}
      />,
    )

    await act(async () => {
      fireEvent.drop(screen.getByTestId('settings-documents-upload-zone'), {
        dataTransfer: {
          files: [file('bad.txt')],
        },
      })
    })

    expect(screen.getByTestId('settings-documents-upload-result')).toHaveAttribute('data-status', 'error')
    expect(screen.getByTestId('settings-documents-upload-result')).toHaveTextContent('upload failed')
  })

  it('loads and displays stats', async () => {
    render(
      <DocumentIngestionPanel
        deletingKnowledgeBase={false}
        deleteKnowledgeBaseConfirming={false}
        onDeleteKnowledgeBase={vi.fn()}
      />,
    )

    await act(async () => {
      fireEvent.click(screen.getByTestId('settings-documents-stats-refresh'))
    })

    expect(getDocStats).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('settings-documents-stats-status')).toHaveTextContent('ready')
    expect(screen.getByTestId('settings-documents-stats-total-docs')).toHaveTextContent('3')
    expect(screen.getByTestId('settings-documents-stats-store-path')).toHaveTextContent('/data/docs')
  })

  it('reflects delete knowledge base button states and clears stats after deletion', async () => {
    const onDeleteKnowledgeBase = vi.fn().mockResolvedValue('deleted')
    const { rerender } = render(
      <DocumentIngestionPanel
        deletingKnowledgeBase={false}
        deleteKnowledgeBaseConfirming={false}
        onDeleteKnowledgeBase={onDeleteKnowledgeBase}
      />,
    )

    await act(async () => {
      fireEvent.click(screen.getByTestId('settings-documents-stats-refresh'))
    })
    expect(screen.getByTestId('settings-documents-stats')).toBeInTheDocument()

    rerender(
      <DocumentIngestionPanel
        deletingKnowledgeBase={true}
        deleteKnowledgeBaseConfirming={true}
        onDeleteKnowledgeBase={onDeleteKnowledgeBase}
      />,
    )
    expect(screen.getByTestId('settings-documents-delete-kb')).toBeDisabled()
    expect(screen.getByTestId('settings-documents-delete-kb')).toHaveTextContent('再次点击确认删除')

    rerender(
      <DocumentIngestionPanel
        deletingKnowledgeBase={false}
        deleteKnowledgeBaseConfirming={true}
        onDeleteKnowledgeBase={onDeleteKnowledgeBase}
      />,
    )

    await act(async () => {
      fireEvent.click(screen.getByTestId('settings-documents-delete-kb'))
    })

    expect(onDeleteKnowledgeBase).toHaveBeenCalledTimes(1)
    expect(screen.queryByTestId('settings-documents-stats')).not.toBeInTheDocument()
  })
})
