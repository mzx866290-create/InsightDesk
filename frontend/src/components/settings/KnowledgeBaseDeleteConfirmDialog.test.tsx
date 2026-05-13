import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { KnowledgeBaseDeleteConfirmDialog } from './KnowledgeBaseDeleteConfirmDialog'

describe('KnowledgeBaseDeleteConfirmDialog', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders chunk delete copy and confirms with chunk id', () => {
    const onCancel = vi.fn()
    const onConfirmChunk = vi.fn()

    render(
      <KnowledgeBaseDeleteConfirmDialog
        confirmDelete={{ type: 'chunk', id: 'chunk-1', label: 'chunk preview' }}
        deletingChunk={null}
        deletingSource={null}
        onCancel={onCancel}
        onConfirmChunk={onConfirmChunk}
        onConfirmSource={vi.fn()}
      />,
    )

    expect(screen.getByText('删除分块')).toBeInTheDocument()
    expect(screen.getByText('确定要删除分块「chunk preview...」吗？此操作不可撤销。')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('kb-delete-confirm-submit'))

    expect(onConfirmChunk).toHaveBeenCalledWith('chunk-1')
    expect(onCancel).not.toHaveBeenCalled()
  })

  it('renders source delete copy and confirms with source name', () => {
    const onCancel = vi.fn()
    const onConfirmSource = vi.fn()

    render(
      <KnowledgeBaseDeleteConfirmDialog
        confirmDelete={{ type: 'source', source: 'doc-a.md' }}
        deletingChunk={null}
        deletingSource={null}
        onCancel={onCancel}
        onConfirmChunk={vi.fn()}
        onConfirmSource={onConfirmSource}
      />,
    )

    expect(screen.getByText('删除整个文档')).toBeInTheDocument()
    expect(screen.getByText('确定要删除文档「doc-a.md」的所有分块吗？此操作不可撤销。')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('kb-delete-confirm-submit'))

    expect(onConfirmSource).toHaveBeenCalledWith('doc-a.md')
    expect(onCancel).not.toHaveBeenCalled()
  })

  it('cancels from the cancel button and backdrop', () => {
    const onCancel = vi.fn()

    render(
      <KnowledgeBaseDeleteConfirmDialog
        confirmDelete={{ type: 'chunk', id: 'chunk-1', label: 'chunk preview' }}
        deletingChunk={null}
        deletingSource={null}
        onCancel={onCancel}
        onConfirmChunk={vi.fn()}
        onConfirmSource={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByTestId('kb-delete-confirm-cancel'))
    fireEvent.click(screen.getByTestId('kb-delete-confirm-dialog'))

    expect(onCancel).toHaveBeenCalledTimes(2)
  })

  it('shows loading and disables actions when the matching delete is in progress', () => {
    render(
      <KnowledgeBaseDeleteConfirmDialog
        confirmDelete={{ type: 'source', source: 'doc-a.md' }}
        deletingChunk={null}
        deletingSource="doc-a.md"
        onCancel={vi.fn()}
        onConfirmChunk={vi.fn()}
        onConfirmSource={vi.fn()}
      />,
    )

    expect(screen.getByTestId('kb-delete-confirm-cancel')).toBeDisabled()
    expect(screen.getByTestId('kb-delete-confirm-submit')).toBeDisabled()
    expect(screen.getByTestId('kb-delete-confirm-submit')).toHaveTextContent('确认删除')
  })
})
