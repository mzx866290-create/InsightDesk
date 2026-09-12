import { Modal } from '../../ui/Modal'

interface HeaderMobileActionsModalProps {
  open: boolean
  panelsCount: number
  currentSessionId: string | null
  sharingSession: boolean
  sessionShareCopied: boolean
  generatingDeck: boolean
  isDeckTaskActive: boolean
  resetting: boolean
  resetConfirm: boolean
  theme: 'dark' | 'light' | 'system'
  onClose: () => void
  onAddPanel: () => void
  onRemovePanel: () => void
  onOpenTaskCenter: () => void
  onOpenKnowledgeBase: () => void
  onOpenSettings: () => void
  onShareSession: () => void | Promise<void>
  onGenerateReport: () => void | Promise<void>
  onResetSession: () => void | Promise<void>
  onSetTheme: (theme: 'dark' | 'light' | 'system') => void
}

export function HeaderMobileActionsModal({
  open,
  panelsCount,
  currentSessionId,
  sharingSession,
  sessionShareCopied,
  generatingDeck,
  isDeckTaskActive,
  resetting,
  resetConfirm,
  theme,
  onClose,
  onAddPanel,
  onRemovePanel,
  onOpenTaskCenter,
  onOpenKnowledgeBase,
  onOpenSettings,
  onShareSession,
  onGenerateReport,
  onResetSession,
  onSetTheme,
}: HeaderMobileActionsModalProps) {
  const closeAfter = (action: () => void | Promise<void>) => {
    void action()
    onClose()
  }

  return (
    <Modal open={open} onClose={onClose} title="快捷操作" width="max-w-md">
      <div className="space-y-4">
        <div>
          <div className="mb-2 text-xs font-medium text-text-secondary">布局与工具</div>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => closeAfter(onAddPanel)}
              disabled={panelsCount >= 6}
              className="rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-hover disabled:opacity-40"
            >
              增加面板
            </button>
            <button
              onClick={() => closeAfter(onRemovePanel)}
              disabled={panelsCount <= 1}
              className="rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-hover disabled:opacity-40"
            >
              减少面板
            </button>
            <button
              onClick={() => closeAfter(onOpenTaskCenter)}
              className="rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-hover"
            >
              任务中心
            </button>
            <button
              onClick={() => closeAfter(onOpenKnowledgeBase)}
              className="rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-hover"
            >
              知识库管理
            </button>
            <button
              onClick={() => closeAfter(onOpenSettings)}
              className="rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-hover"
            >
              设置
            </button>
          </div>
        </div>

        <div>
          <div className="mb-2 text-xs font-medium text-text-secondary">会话操作</div>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => closeAfter(onShareSession)}
              disabled={!currentSessionId || sharingSession}
              className="rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-hover disabled:opacity-40"
            >
              {sessionShareCopied ? '已复制链接' : '分享会话'}
            </button>
            <button
              onClick={() => closeAfter(onGenerateReport)}
              disabled={!currentSessionId || generatingDeck || isDeckTaskActive}
              className="rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-hover disabled:opacity-40"
            >
              生成演示稿
            </button>
            <button
              onClick={() => closeAfter(onResetSession)}
              disabled={!currentSessionId || resetting}
              className="rounded-xl border border-accent-red/20 bg-bg-primary px-3 py-2 text-sm text-accent-red transition-colors hover:bg-accent-red/5 disabled:opacity-40"
            >
              {resetConfirm ? '确认重置？' : '重置会话'}
            </button>
          </div>
        </div>

        <div>
          <div className="mb-2 text-xs font-medium text-text-secondary">主题</div>
          <div className="grid grid-cols-3 gap-2">
            {([
              ['dark', '深色'],
              ['light', '浅色'],
              ['system', '跟随系统'],
            ] as const).map(([value, label]) => (
              <button
                key={value}
                onClick={() => onSetTheme(value)}
                className={`rounded-xl border px-3 py-2 text-sm transition-colors ${
                  theme === value
                    ? 'border-accent-blue/40 bg-accent-blue/15 text-accent-blue'
                    : 'border-bg-border bg-bg-primary text-text-primary hover:bg-bg-hover'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </Modal>
  )
}
