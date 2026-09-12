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
    expect(screen.getByTestId('settings-kb-tab-documents')).toHaveClass('min-h-11')
    expect(screen.getByTestId('settings-kb-tab-monitor')).toHaveAccessibleName('监控与检索')
    expect(screen.getByText('文档列表')).toBeInTheDocument()
    expect(screen.getByText('上传文档')).toBeInTheDocument()
    expect(screen.getByText('监控与检索')).toBeInTheDocument()
  })

  it('emits tab changes', () => {
    const onTabChange = vi.fn()

    render(<KnowledgeBaseTabs activeTab="documents" onTabChange={onTabChange} />)

    fireEvent.click(screen.getByTestId('settings-kb-tab-monitor'))

    expect(onTabChange).toHaveBeenCalledWith('monitor')
  })
})
