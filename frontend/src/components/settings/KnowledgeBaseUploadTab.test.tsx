import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { getTask, uploadDocuments, type TaskRecord } from '../../api/client'
import { KnowledgeBaseUploadTab } from './KnowledgeBaseUploadTab'

vi.mock('../../api/client', () => ({
  getTask: vi.fn(),
  uploadDocuments: vi.fn(),
}))

const task = (patch: Partial<TaskRecord> = {}): TaskRecord => ({
  task_id: 'task-1',
  task_type: 'document_upload',
  status: 'running',
  progress: 0.42,
  created_at: 1,
  ...patch,
})

const file = (name: string, size: number): File => (
  new File(['a'.repeat(size)], name, { type: 'text/plain' })
)

describe('KnowledgeBaseUploadTab', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    vi.mocked(uploadDocuments).mockResolvedValue({
      ok: true,
      task_id: 'task-1',
      task_type: 'document_upload',
      status: 'pending',
      message: 'queued',
    })
    vi.mocked(getTask).mockResolvedValue(task())
  })

  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  it('keeps file removal, upload payload, and progress display behavior', async () => {
    render(<KnowledgeBaseUploadTab />)

    const input = screen.getByTestId('settings-kb-upload-input') as HTMLInputElement

    fireEvent.change(input, {
      target: {
        files: [
          file('intro.md', 2048),
          file('diagram.png', 3072),
        ],
      },
    })

    expect(screen.getByText('intro.md')).toBeInTheDocument()
    expect(screen.getByText('diagram.png')).toBeInTheDocument()

    const introRow = screen.getByText('intro.md').closest('div')
    expect(introRow).not.toBeNull()
    fireEvent.click(within(introRow as HTMLElement).getByRole('button'))

    expect(screen.queryByText('intro.md')).not.toBeInTheDocument()
    expect(screen.getByText('diagram.png')).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getByTestId('settings-kb-upload-submit'))
      await Promise.resolve()
    })

    expect(uploadDocuments).toHaveBeenCalledTimes(1)
    expect(vi.mocked(uploadDocuments).mock.calls[0][0].map(selectedFile => selectedFile.name)).toEqual(['diagram.png'])

    await act(async () => {
      vi.advanceTimersByTime(800)
      await Promise.resolve()
    })

    expect(getTask).toHaveBeenCalledWith('task-1')
    expect(screen.getByTestId('settings-kb-upload-status')).toHaveClass('text-accent-blue')
    expect(screen.getByTestId('settings-kb-upload-percent')).toHaveTextContent('42%')
  })

  it('tracks drag state with a stable upload zone test id', () => {
    render(<KnowledgeBaseUploadTab />)

    const zone = screen.getByTestId('settings-kb-upload-zone')

    fireEvent.dragOver(zone)
    expect(zone).toHaveClass('border-accent-blue')

    fireEvent.dragLeave(zone)
    expect(zone).toHaveClass('border-bg-border')
  })

  it('clears selected files and notifies after a completed upload task', async () => {
    const onUploaded = vi.fn()
    vi.mocked(getTask).mockResolvedValueOnce(task({
      status: 'completed',
      progress: 1,
      result: 'done',
    }))

    render(<KnowledgeBaseUploadTab onUploaded={onUploaded} />)

    fireEvent.change(screen.getByTestId('settings-kb-upload-input'), {
      target: {
        files: [file('intro.md', 2048)],
      },
    })

    expect(screen.getByText('intro.md')).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getByTestId('settings-kb-upload-submit'))
      await Promise.resolve()
    })

    await act(async () => {
      vi.advanceTimersByTime(800)
      await Promise.resolve()
    })

    expect(onUploaded).toHaveBeenCalledTimes(1)
    expect(screen.queryByText('intro.md')).not.toBeInTheDocument()
    expect(screen.getByTestId('settings-kb-upload-progress')).toBeInTheDocument()
  })

  it('renders upload errors and forwards admin access errors', async () => {
    const onAdminAccessError = vi.fn()
    vi.mocked(uploadDocuments).mockRejectedValueOnce(new Error('remote admin token required'))

    render(<KnowledgeBaseUploadTab onAdminAccessError={onAdminAccessError} />)

    fireEvent.change(screen.getByTestId('settings-kb-upload-input'), {
      target: {
        files: [file('intro.md', 2048)],
      },
    })

    await act(async () => {
      fireEvent.click(screen.getByTestId('settings-kb-upload-submit'))
      await Promise.resolve()
    })

    expect(screen.getByTestId('settings-kb-upload-error')).toHaveTextContent('remote admin token required')
    expect(onAdminAccessError).toHaveBeenCalledWith('remote admin token required')
    expect(getTask).not.toHaveBeenCalled()
  })
})
