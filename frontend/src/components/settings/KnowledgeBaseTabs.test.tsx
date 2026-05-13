import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { KnowledgeBaseTabs } from './KnowledgeBaseTabs'

describe('KnowledgeBaseTabs', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders all knowledge base tabs and highlights the active tab', () => {
    render(<KnowledgeBaseTabs activeTab="documents" onTabChange={vi.fn()} />)

    expect(screen.getByTestId('settings-kb-tabs')).toBeInTheDocument()
    expect(screen.getByTestId('settings-kb-tab-documents')).toHaveClass('bg-bg-secondary')
    expect(screen.getByText('文档列表')).toBeInTheDocument()
    expect(screen.getByText('上传文档')).toBeInTheDocument()
    expect(screen.getByText('检索测试')).toBeInTheDocument()
    expect(screen.getByText('健康状态')).toBeInTheDocument()
  })

  it('emits tab changes', () => {
    const onTabChange = vi.fn()

    render(<KnowledgeBaseTabs activeTab="documents" onTabChange={onTabChange} />)

    fireEvent.click(screen.getByTestId('settings-kb-tab-health'))

    expect(onTabChange).toHaveBeenCalledWith('health')
  })
})
