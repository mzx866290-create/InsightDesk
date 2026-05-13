import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

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

    const buttons = screen.getAllByRole('button')
    fireEvent.click(buttons[0])
    fireEvent.click(buttons[1])

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

    const firstPageButtons = screen.getAllByRole('button')
    expect(firstPageButtons[0]).toBeDisabled()
    expect(firstPageButtons[1]).toBeDisabled()

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

    const loadingButtons = screen.getAllByRole('button')
    expect(loadingButtons[0]).toBeDisabled()
    expect(loadingButtons[1]).toBeDisabled()
  })
})
