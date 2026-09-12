import React from 'react'
import { Check, FileText, History, MoreHorizontal, RotateCcw, Share2 } from 'lucide-react'

interface HeaderMoreMenuProps {
  open: boolean
  menuRef: React.RefObject<HTMLDivElement | null>
  currentSessionId: string | null
  sharingSession: boolean
  sessionShareCopied: boolean
  generatingDeck: boolean
  isDeckTaskActive: boolean
  resetting: boolean
  resetConfirm: boolean
  onToggle: () => void
  onClose: () => void
  onShareSession: () => void | Promise<void>
  onGenerateReport: () => void | Promise<void>
  onOpenTaskCenter: () => void
  onResetSession: () => void | Promise<void>
}

export function HeaderMoreMenu({
  open,
  menuRef,
  currentSessionId,
  sharingSession,
  sessionShareCopied,
  generatingDeck,
  isDeckTaskActive,
  resetting,
  resetConfirm,
  onToggle,
  onClose,
  onShareSession,
  onGenerateReport,
  onOpenTaskCenter,
  onResetSession,
}: HeaderMoreMenuProps) {
  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={onToggle}
        data-testid="header-more-menu"
        className={`flex h-10 w-10 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary ${
          open ? 'bg-bg-hover text-text-primary' : ''
        }`}
        title="更多操作"
      >
        <MoreHorizontal size={16} />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-30 mt-1 min-w-[160px] overflow-hidden rounded-xl border border-bg-border bg-bg-primary shadow-xl">
          <button
            onClick={() => {
              void onShareSession()
              onClose()
            }}
            disabled={!currentSessionId || sharingSession}
            className="flex w-full items-center gap-2 px-3 py-2 text-xs text-text-primary transition-colors hover:bg-bg-hover disabled:opacity-40"
          >
            {sessionShareCopied ? (
              <Check size={13} className="text-accent-green" />
            ) : (
              <Share2 size={13} />
            )}
            {sessionShareCopied ? '已复制链接' : '分享会话'}
          </button>
          <button
            onClick={() => {
              void onGenerateReport()
              onClose()
            }}
            disabled={generatingDeck || isDeckTaskActive || !currentSessionId}
            className="flex w-full items-center gap-2 px-3 py-2 text-xs text-text-primary transition-colors hover:bg-bg-hover disabled:opacity-40"
          >
            <FileText size={13} />
            生成演示稿
          </button>
          <button
            onClick={() => {
              onOpenTaskCenter()
              onClose()
            }}
            data-testid="header-open-task-center"
            className="flex w-full items-center gap-2 px-3 py-2 text-xs text-text-primary transition-colors hover:bg-bg-hover"
          >
            <History size={13} />
            任务中心
          </button>
          <div className="mx-2 border-t border-bg-border" />
          <button
            onClick={() => {
              void onResetSession()
              onClose()
            }}
            disabled={resetting || !currentSessionId}
            className={`flex w-full items-center gap-2 px-3 py-2 text-xs transition-colors hover:bg-bg-hover disabled:opacity-40 ${
              resetConfirm ? 'text-accent-red' : 'text-text-primary'
            }`}
          >
            <RotateCcw size={13} />
            {resetConfirm ? '确认重置？' : '重置会话'}
          </button>
        </div>
      )}
    </div>
  )
}
