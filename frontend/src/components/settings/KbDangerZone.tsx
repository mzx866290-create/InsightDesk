import React from 'react'
import { Trash2 } from 'lucide-react'
import { Button } from '../ui/Button'

export interface KbDangerZoneProps {
  deleting: boolean
  confirming: boolean
  onDelete: () => void
}

export function KbDangerZone({ deleting, confirming, onDelete }: KbDangerZoneProps) {
  return (
    <div className="border-t border-bg-border pt-4" data-testid="settings-kb-danger-zone">
      <Button
        variant="ghost"
        onClick={onDelete}
        loading={deleting}
        className={`gap-2 w-full justify-center ${
          confirming
            ? 'text-accent-red border border-accent-red/40 bg-accent-red/5'
            : 'text-accent-red/60 hover:text-accent-red'
        }`}
        data-testid="settings-kb-delete"
      >
        <Trash2 size={13} />
        {confirming ? '再次点击确认删除' : '删除当前知识库'}
      </Button>
      <p className="text-[11px] text-text-secondary/50 text-center mt-1">
        此操作无法撤销，并会删除所有向量索引文件。
      </p>
    </div>
  )
}
