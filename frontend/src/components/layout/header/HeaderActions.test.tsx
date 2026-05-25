import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HeaderMobileActionsModal } from './HeaderMobileActionsModal'
import { HeaderMoreMenu } from './HeaderMoreMenu'

function renderMobileActions(
  overrides: Partial<React.ComponentProps<typeof HeaderMobileActionsModal>> = {},
) {
  return render(
    <HeaderMobileActionsModal
      open
      panelsCount={2}
      currentSessionId="session-1"
      sharingSession={false}
      sessionShareCopied={false}
      generatingDeck={false}
      isDeckTaskActive={false}
      resetting={false}
      resetConfirm={false}
      theme="system"
      onClose={vi.fn()}
      onAddPanel={vi.fn()}
      onRemovePanel={vi.fn()}
      onOpenTaskCenter={vi.fn()}
      onOpenKnowledgeBase={vi.fn()}
      onOpenSettings={vi.fn()}
      onShareSession={vi.fn()}
      onGenerateReport={vi.fn()}
      onResetSession={vi.fn()}
      onNewChat={vi.fn()}
      onSetTheme={vi.fn()}
      {...overrides}
    />,
  )
}

function renderMoreMenu(overrides: Partial<React.ComponentProps<typeof HeaderMoreMenu>> = {}) {
  return render(
    <HeaderMoreMenu
      open
      menuRef={{ current: null }}
      currentSessionId="session-1"
      sharingSession={false}
      sessionShareCopied={false}
      generatingDeck={false}
      isDeckTaskActive={false}
      resetting={false}
      resetConfirm={false}
      onToggle={vi.fn()}
      onClose={vi.fn()}
      onShareSession={vi.fn()}
      onGenerateReport={vi.fn()}
      onOpenTaskCenter={vi.fn()}
      onResetSession={vi.fn()}
      {...overrides}
    />,
  )
}

describe('Header action surfaces', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders mobile actions and closes after navigation-style actions', () => {
    const onClose = vi.fn()
    const onOpenKnowledgeBase = vi.fn()

    renderMobileActions({ onClose, onOpenKnowledgeBase })

    expect(screen.getByText('快捷操作')).toBeInTheDocument()
    expect(screen.getByText('布局与工具')).toBeInTheDocument()
    expect(screen.getByText('会话操作')).toBeInTheDocument()

    fireEvent.click(screen.getByText('知识库管理'))

    expect(onOpenKnowledgeBase).toHaveBeenCalledTimes(1)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('keeps mobile theme selection local to the theme control', () => {
    const onClose = vi.fn()
    const onSetTheme = vi.fn()

    renderMobileActions({ onClose, onSetTheme })

    fireEvent.click(screen.getByText('浅色'))

    expect(onSetTheme).toHaveBeenCalledWith('light')
    expect(onClose).not.toHaveBeenCalled()
  })

  it('disables session actions in the mobile modal without an active session', () => {
    renderMobileActions({ currentSessionId: null })

    expect(screen.getByText('分享会话')).toBeDisabled()
    expect(screen.getByText('生成演示稿')).toBeDisabled()
    expect(screen.getByText('重置会话')).toBeDisabled()
  })

  it('routes desktop more-menu actions through their callbacks and closes the menu', () => {
    const onClose = vi.fn()
    const onShareSession = vi.fn()

    renderMoreMenu({ onClose, onShareSession })

    fireEvent.click(screen.getByText('分享会话'))

    expect(onShareSession).toHaveBeenCalledTimes(1)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('shows the reset confirmation state in the desktop more menu', () => {
    renderMoreMenu({ resetConfirm: true })

    expect(screen.getByText('确认重置？')).toHaveClass('text-accent-red')
  })
})
