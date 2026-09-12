import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Session } from '../../../api/client'
import { SessionItemRow } from './SessionItemRow'

const session = {
  session_id: 'session-1',
  title: '项目讨论',
  workspace_id: 'workspace-1',
  created_at: 1,
  updated_at: 1,
  message_count: 2,
  session_order: 0,
  tags: [],
  is_pinned: false,
  is_favorite: false,
  is_archived: false,
} as Session

const createProps = (
  overrides: Partial<React.ComponentProps<typeof SessionItemRow>> = {},
): React.ComponentProps<typeof SessionItemRow> => ({
  session,
  isActive: true,
  isEditing: false,
  showActions: true,
  actionsMenuOpen: false,
  canDragSort: false,
  hasDraggingSession: false,
  isDragging: false,
  isDragOver: false,
  editingTitle: '',
  editingTags: '',
  search: '',
  movingSessionId: null,
  savingId: null,
  exportingId: null,
  deletingId: null,
  workspaces: [],
  workspaceNameMap: new Map(),
  formatTime: () => '刚刚',
  onSelectSession: vi.fn(),
  onToggleActionsMenu: vi.fn(),
  onCloseActionsMenu: vi.fn(),
  onStartDraggingSession: vi.fn(),
  onDragOverSession: vi.fn(),
  onClearDragOver: vi.fn(),
  onDropSession: vi.fn(),
  onEndDragging: vi.fn(),
  onHoverSession: vi.fn(),
  onEditingTitleChange: vi.fn(),
  onEditingTagsChange: vi.fn(),
  onEditKeyDown: vi.fn(),
  onCancelEditing: vi.fn(),
  onSaveEditing: vi.fn(),
  onPatchSession: vi.fn(),
  onToggleMoveSession: vi.fn(),
  onStartEditing: vi.fn(),
  onExportSession: vi.fn(),
  onDeleteSession: vi.fn(),
  onMoveSession: vi.fn(),
  ...overrides,
})

describe('SessionItemRow', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('keeps pin and favorite visible and groups low-frequency actions', () => {
    const onToggleActionsMenu = vi.fn()
    const onPatchSession = vi.fn()
    const closedProps = createProps({ onToggleActionsMenu, onPatchSession })
    const { rerender } = render(<SessionItemRow {...closedProps} />)

    expect(screen.getByTitle('置顶会话')).toBeInTheDocument()
    expect(screen.getByTitle('收藏对话')).toBeInTheDocument()
    expect(screen.queryByTestId('session-actions-menu')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTitle('更多会话操作'))
    expect(onToggleActionsMenu).toHaveBeenCalledWith('session-1')

    rerender(<SessionItemRow {...closedProps} actionsMenuOpen />)

    const menu = screen.getByTestId('session-actions-menu')
    expect(menu).toBeInTheDocument()
    expect(screen.getByText('移动到工作区')).toHaveClass('min-h-11')

    fireEvent.click(screen.getByText('归档对话'))
    expect(onPatchSession).toHaveBeenCalledWith(
      expect.anything(),
      'session-1',
      { is_archived: true },
    )
  })
})
