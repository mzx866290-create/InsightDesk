import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useChatStore } from '../../stores/chatStore'
import { KbChunkPagination } from './KbChunkPagination'

vi.mock('../ui/Button', () => ({
  Button: ({
    children,
    variant: _variant,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: string
  }) => <button {...props}>{children}</button>,
}))

describe('KbChunkPagination', () => {
  beforeEach(() => {
    useChatStore.setState({ language: 'zh-CN' })
  })

  afterEach(() => {
    cleanup()
  })

  it('forwards previous and next page actions', () => {
    const onPreviousPage = vi.fn()
    const onNextPage = vi.fn()

    render(
      <KbChunkPagination
        pagination={{ currentPage: 2, totalPages: 5, previousOffset: 0, nextOffset: 24 }}
        offset={12}
        total={60}
        loading={false}
        onPreviousPage={onPreviousPage}
        onNextPage={onNextPage}
      />,
    )

    const previousButton = screen.getByRole('button', { name: '上一页' })
    const nextButton = screen.getByRole('button', { name: '下一页' })
    fireEvent.click(previousButton)
    fireEvent.click(nextButton)

    expect(screen.getByText('第 2 / 5 页，共 60 条')).toBeInTheDocument()
    expect(previousButton).toHaveClass('min-h-11')
    expect(nextButton).toHaveClass('min-h-11')
    expect(onPreviousPage).toHaveBeenCalledTimes(1)
    expect(onNextPage).toHaveBeenCalledTimes(1)
  })

  it('disables edge page actions', () => {
    const { rerender } = render(
      <KbChunkPagination
        pagination={{ currentPage: 1, totalPages: 1, previousOffset: 0, nextOffset: 12 }}
        offset={0}
        total={5}
        loading={false}
        onPreviousPage={vi.fn()}
        onNextPage={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: '上一页' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '下一页' })).toBeDisabled()

    rerender(
      <KbChunkPagination
        pagination={{ currentPage: 1, totalPages: 2, previousOffset: 0, nextOffset: 12 }}
        offset={0}
        total={24}
        loading
        onPreviousPage={vi.fn()}
        onNextPage={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: '上一页' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '下一页' })).toBeDisabled()
  })
})
