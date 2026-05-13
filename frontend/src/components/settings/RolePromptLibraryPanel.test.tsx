import React from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { SystemPrompt } from '../../api/client'
import { RolePromptLibraryPanel } from './RolePromptLibraryPanel'
import type { RolePromptTemplate } from './useRolePrompts'

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

const prompts: SystemPrompt[] = [
  {
    id: 'active-role',
    name: 'Active Role',
    content: 'Currently active prompt.',
    is_default: true,
    is_active: true,
    created_at: 1,
    updated_at: 2,
    dashboard_template: {
      enabled: true,
      title_hint: 'Dashboard',
      focus_metrics: [],
      preferred_charts: ['bar'],
      section_order: ['summary'],
      audience_tone: 'business',
    },
  },
  {
    id: 'editable-role',
    name: 'Editable Role',
    content: 'Editable prompt content.',
    is_default: false,
    is_active: false,
    created_at: 3,
    updated_at: 4,
    vector_store_id: 'kb-1',
  },
]

const quickTemplates: RolePromptTemplate[] = [
  {
    name: 'Quick Role',
    content: 'Use this prompt.',
  },
]

function renderPanel(overrides: Partial<React.ComponentProps<typeof RolePromptLibraryPanel>> = {}) {
  return render(
    <RolePromptLibraryPanel
      loading={false}
      prompts={prompts}
      editing={false}
      activatingId={null}
      deletingPromptId={null}
      activateStatus={{}}
      quickTemplates={quickTemplates}
      onCreate={vi.fn()}
      onActivate={vi.fn()}
      onEdit={vi.fn()}
      onDelete={vi.fn()}
      {...overrides}
    />,
  )
}

describe('RolePromptLibraryPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders prompt rows and status badges', () => {
    renderPanel({ activateStatus: { 'editable-role': 'loaded' } })

    const rows = screen.getAllByTestId('settings-role-prompt-row')
    expect(rows).toHaveLength(2)

    expect(within(rows[0]).getByText('Active Role')).toBeInTheDocument()
    expect(within(rows[0]).getByText('当前使用')).toBeInTheDocument()
    expect(within(rows[0]).getByText('内置')).toBeInTheDocument()
    expect(within(rows[0]).getByText('看板已启用')).toBeInTheDocument()

    expect(within(rows[1]).getByText('Editable Role')).toBeInTheDocument()
    expect(within(rows[1]).getByText('已绑定知识库')).toBeInTheDocument()
    expect(within(rows[1]).getByText('知识库 已加载')).toBeInTheDocument()
  })

  it('forwards create, template, activate, edit, and delete actions', () => {
    const onCreate = vi.fn()
    const onActivate = vi.fn()
    const onEdit = vi.fn()
    const onDelete = vi.fn()

    renderPanel({ onCreate, onActivate, onEdit, onDelete })

    fireEvent.click(screen.getByTestId('settings-role-prompt-create'))
    fireEvent.click(screen.getByTestId('settings-role-prompt-quick-template'))

    const editableRow = screen.getAllByTestId('settings-role-prompt-row')[1]
    fireEvent.click(within(editableRow).getByTestId('settings-role-prompt-activate'))
    fireEvent.click(within(editableRow).getByTestId('settings-role-prompt-edit'))
    fireEvent.click(within(editableRow).getByTestId('settings-role-prompt-delete'))

    expect(onCreate).toHaveBeenNthCalledWith(1)
    expect(onCreate).toHaveBeenNthCalledWith(2, quickTemplates[0])
    expect(onActivate).toHaveBeenCalledWith('editable-role')
    expect(onEdit).toHaveBeenCalledWith(prompts[1])
    expect(onDelete).toHaveBeenCalledWith('editable-role')
  })

  it('hides create and quick templates while editing', () => {
    renderPanel({ editing: true })

    expect(screen.queryByTestId('settings-role-prompt-create')).not.toBeInTheDocument()
    expect(screen.queryByTestId('settings-role-prompt-quick-template')).not.toBeInTheDocument()
  })

  it('shows the loading state instead of prompt rows', () => {
    renderPanel({ loading: true })

    expect(screen.queryByTestId('settings-role-prompt-row')).not.toBeInTheDocument()
  })
})
