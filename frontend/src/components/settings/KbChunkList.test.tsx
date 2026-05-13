import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { KnowledgeBaseChunk } from '../../api/client'
import { KbChunkList } from './KbChunkList'

vi.mock('../ui/Button', () => ({
  Button: ({
    children,
    loading = false,
    variant: _variant,
    disabled,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    loading?: boolean
    variant?: string
  }) => (
    <button disabled={disabled || loading} {...props}>
      {children}
    </button>
  ),
}))

const chunk: KnowledgeBaseChunk = {
  chunk_id: 'chunk-1',
  position: 0,
  source: 'manual.md',
  content: 'Full chunk content',
  preview: 'Chunk preview',
  char_count: 18,
  metadata: {},
}

function renderList(overrides: Partial<React.ComponentProps<typeof KbChunkList>> = {}) {
  const props: React.ComponentProps<typeof KbChunkList> = {
    chunks: [chunk],
    loading: false,
    editingChunkId: null,
    editingChunkContent: '',
    editingChunkSource: '',
    savingChunkId: null,
    deleteConfirmId: null,
    deletingChunkId: null,
    onEditingContentChange: vi.fn(),
    onEditingSourceChange: vi.fn(),
    onStartEdit: vi.fn(),
    onCancelEdit: vi.fn(),
    onSave: vi.fn(),
    onDelete: vi.fn(),
    ...overrides,
  }

  return {
    props,
    ...render(<KbChunkList {...props} />),
  }
}

describe('KbChunkList', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders empty, loading, and preview states', () => {
    const { rerender, props } = renderList({ chunks: [], loading: false })

    expect(screen.getByTestId('settings-kb-chunk-empty')).toBeInTheDocument()

    rerender(<KbChunkList {...props} chunks={[]} loading />)
    expect(screen.queryByTestId('settings-kb-chunk-empty')).not.toBeInTheDocument()

    rerender(<KbChunkList {...props} chunks={[chunk]} loading={false} />)
    expect(screen.getByTestId('settings-kb-chunk-list')).toBeInTheDocument()
    expect(screen.getByTestId('settings-kb-chunk-preview')).toHaveTextContent('Chunk preview')
  })

  it('forwards edit and delete actions', () => {
    const onStartEdit = vi.fn()
    const onDelete = vi.fn()

    renderList({ onStartEdit, onDelete })

    fireEvent.click(screen.getByTestId('settings-kb-chunk-edit'))
    fireEvent.click(screen.getByTestId('settings-kb-chunk-delete'))

    expect(onStartEdit).toHaveBeenCalledWith(chunk)
    expect(onDelete).toHaveBeenCalledWith('chunk-1')
  })

  it('renders edit mode and forwards edited source/content, save, and cancel', () => {
    const onEditingSourceChange = vi.fn()
    const onEditingContentChange = vi.fn()
    const onSave = vi.fn()
    const onCancelEdit = vi.fn()

    renderList({
      editingChunkId: 'chunk-1',
      editingChunkSource: 'manual.md',
      editingChunkContent: 'Draft content',
      onEditingSourceChange,
      onEditingContentChange,
      onSave,
      onCancelEdit,
    })

    fireEvent.change(screen.getByTestId('settings-kb-chunk-edit-source'), {
      target: { value: 'updated.md' },
    })
    fireEvent.change(screen.getByTestId('settings-kb-chunk-edit-content'), {
      target: { value: 'Updated content' },
    })
    fireEvent.click(screen.getByTestId('settings-kb-chunk-edit-save'))
    fireEvent.click(screen.getByTestId('settings-kb-chunk-edit-cancel'))

    expect(onEditingSourceChange).toHaveBeenCalledWith('updated.md')
    expect(onEditingContentChange).toHaveBeenCalledWith('Updated content')
    expect(onSave).toHaveBeenCalledTimes(1)
    expect(onCancelEdit).toHaveBeenCalledTimes(1)
  })

  it('preserves row confirmation, deleting, and saving states', () => {
    renderList({
      editingChunkId: 'chunk-1',
      savingChunkId: 'chunk-1',
      deleteConfirmId: 'chunk-1',
      deletingChunkId: 'chunk-1',
    })

    expect(screen.queryByTestId('settings-kb-chunk-edit')).not.toBeInTheDocument()
    expect(screen.getByTestId('settings-kb-chunk-delete')).toHaveAttribute('data-confirming', 'true')
    expect(screen.getByTestId('settings-kb-chunk-delete')).toBeDisabled()
    expect(screen.getByTestId('settings-kb-chunk-edit-save')).toBeDisabled()
  })
})
