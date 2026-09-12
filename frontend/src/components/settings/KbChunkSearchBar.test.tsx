import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useChatStore } from '../../stores/chatStore'
import { KbChunkSearchBar } from './KbChunkSearchBar'

vi.mock('../ui/Button', () => ({
  Button: ({
    children,
    loading: _loading,
    variant: _variant,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    loading?: boolean
    variant?: string
  }) => <button {...props}>{children}</button>,
}))

describe('KbChunkSearchBar', () => {
  beforeEach(() => {
    useChatStore.setState({ language: 'zh-CN' })
  })

  afterEach(() => {
    cleanup()
  })

  it('forwards query, source, search, and refresh actions', () => {
    const onQueryChange = vi.fn()
    const onSourceFilterChange = vi.fn()
    const onSearch = vi.fn()
    const onRefresh = vi.fn()

    render(
      <KbChunkSearchBar
        loading={false}
        query=""
        sourceFilter=""
        sourceOptions={['manual.md', 'ops.md']}
        onQueryChange={onQueryChange}
        onSourceFilterChange={onSourceFilterChange}
        onSearch={onSearch}
        onRefresh={onRefresh}
      />,
    )

    fireEvent.change(screen.getByTestId('settings-kb-chunk-query'), {
      target: { value: 'incident' },
    })
    fireEvent.keyDown(screen.getByTestId('settings-kb-chunk-query'), { key: 'Enter' })
    fireEvent.change(screen.getByTestId('settings-kb-chunk-source-filter'), {
      target: { value: 'ops.md' },
    })
    fireEvent.click(screen.getByTestId('settings-kb-chunk-search'))
    fireEvent.click(screen.getByTestId('settings-kb-chunk-refresh'))

    expect(screen.getByText('知识库切片浏览器')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('搜索切片内容或来源...')).toHaveClass('min-h-11')
    expect(screen.getByRole('option', { name: '全部来源' })).toBeInTheDocument()
    expect(screen.getByTestId('settings-kb-chunk-search')).toHaveClass('min-h-11')
    expect(screen.getByTestId('settings-kb-chunk-refresh')).toHaveClass('min-h-11')
    expect(onQueryChange).toHaveBeenCalledWith('incident')
    expect(onSourceFilterChange).toHaveBeenCalledWith('ops.md')
    expect(onSearch).toHaveBeenCalledTimes(2)
    expect(onRefresh).toHaveBeenCalledTimes(1)
  })
})
