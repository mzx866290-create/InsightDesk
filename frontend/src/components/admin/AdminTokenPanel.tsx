import React from 'react'

import { Button } from '../ui/Button'

interface AdminTokenPanelProps {
  token: string
  saved: boolean
  error?: string | null
  description: string
  onTokenChange: (value: string) => void
  onSave: () => void
  onClear: () => void
}

export const AdminTokenPanel: React.FC<AdminTokenPanelProps> = ({
  token,
  saved,
  error,
  description,
  onTokenChange,
  onSave,
  onClear,
}) => {
  const configured = token.trim().length > 0

  return (
    <div className="rounded-xl border border-bg-border bg-bg-tertiary/30 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">远程管理员令牌</h3>
          <p className="mt-1 text-xs leading-5 text-text-secondary">{description}</p>
        </div>
        <span className={`rounded-full px-2 py-1 text-[11px] ${
          configured
            ? 'bg-accent-green/10 text-accent-green'
            : 'bg-bg-secondary text-text-secondary'
        }`}>
          {configured ? '已保存' : '未配置'}
        </span>
      </div>

      <div className="mt-4 flex gap-2">
        <input
          className="input-base flex-1 text-sm"
          type="password"
          placeholder="输入 ADMIN_API_TOKEN"
          value={token}
          onChange={(e) => onTokenChange(e.target.value)}
        />
        <Button variant="primary" onClick={onSave}>
          {saved ? '已保存' : '保存令牌'}
        </Button>
        <Button variant="ghost" onClick={onClear}>
          清除
        </Button>
      </div>

      <p className="mt-2 text-[11px] text-text-secondary">
        令牌只保存在当前浏览器的本地存储中，不会回写到服务器配置。
      </p>

      {error && (
        <div className="mt-3 rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red">
          {error}
        </div>
      )}
    </div>
  )
}
