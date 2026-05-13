import { Loader2, Search } from 'lucide-react'

import { Button } from '../ui/Button'
import type { KbRetrievalControlsVariant } from './KbRetrievalControlsModel'

const TAB_RUN_BUTTON_CLASS_NAME =
  'px-4 py-2 rounded-lg text-sm font-medium bg-accent-blue text-white hover:bg-accent-blue/80 disabled:opacity-50 transition-colors flex items-center gap-1.5'

interface KbRetrievalRunButtonProps {
  disabled: boolean
  loading: boolean
  label: string
  testId?: string
  variant: KbRetrievalControlsVariant
  onClick: () => void | Promise<void>
}

export function KbRetrievalRunButton({
  disabled,
  loading,
  label,
  testId,
  variant,
  onClick,
}: KbRetrievalRunButtonProps) {
  if (variant === 'diagnostic') {
    return (
      <Button
        variant="primary"
        onClick={() => void onClick()}
        loading={loading}
        disabled={disabled}
        data-testid={testId}
      >
        <Search size={13} />
        {label}
      </Button>
    )
  }

  return (
    <button
      onClick={() => void onClick()}
      disabled={disabled || loading}
      className={TAB_RUN_BUTTON_CLASS_NAME}
      data-testid={testId}
    >
      {loading ? <Loader2 size={13} className="animate-spin" /> : <Search size={13} />}
      {label}
    </button>
  )
}
