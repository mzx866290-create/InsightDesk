import React, { useEffect, useState } from 'react'
import { Database, Layers3, Palette } from 'lucide-react'
import { getConnectionTypeLabel } from '../../api/client'
import type { ModelConfig } from '../../api/client'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'

interface PanelOption {
  id: string
  modelConfig: ModelConfig
}

interface DeckGenerationModalProps {
  open: boolean
  panels: PanelOption[]
  knowledgeBaseEnabled: boolean
  initialPanelId?: string
  initialTheme?: 'default' | 'midnight' | 'sunrise'
  initialSlideCount?: number
  onClose: () => void
  onSubmit: (payload: {
    panel_config: ModelConfig
    target_slide_count: number
    theme: 'default' | 'midnight' | 'sunrise'
  }) => Promise<void> | void
}

const DECK_THEMES = [
  {
    value: 'default',
    label: '经典蓝图',
    description: '清爽蓝白，适合通用汇报。',
    preview: 'from-slate-50 via-white to-blue-50 border-blue-100',
  },
  {
    value: 'midnight',
    label: '深夜简报',
    description: '深色高对比，适合战略或技术汇报。',
    preview: 'from-slate-950 via-slate-900 to-sky-950 border-slate-700',
  },
  {
    value: 'sunrise',
    label: '晨曦回顾',
    description: '暖色评审风格，适合复盘和业务回顾。',
    preview: 'from-orange-50 via-amber-50 to-rose-100 border-orange-200',
  },
] as const

export const DeckGenerationModal: React.FC<DeckGenerationModalProps> = ({
  open,
  panels,
  knowledgeBaseEnabled,
  initialPanelId,
  initialTheme = 'default',
  initialSlideCount = 8,
  onClose,
  onSubmit,
}) => {
  const [selectedPanelId, setSelectedPanelId] = useState('')
  const [targetSlideCount, setTargetSlideCount] = useState(8)
  const [selectedTheme, setSelectedTheme] = useState<'default' | 'midnight' | 'sunrise'>('default')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open) return
    setSelectedPanelId(initialPanelId || panels[0]?.id || '')
    setTargetSlideCount(Math.max(4, Math.min(10, initialSlideCount)))
    setSelectedTheme(initialTheme)
  }, [initialPanelId, initialSlideCount, initialTheme, open, panels])

  const selectedPanel = panels.find((panel) => panel.id === selectedPanelId) ?? panels[0] ?? null

  const handleSubmit = async () => {
    if (!selectedPanel) return
    setSubmitting(true)
    try {
      await onSubmit({
        panel_config: selectedPanel.modelConfig,
        target_slide_count: targetSlideCount,
        theme: selectedTheme,
      })
      onClose()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal open={open} onClose={() => !submitting && onClose()} title="生成演示稿" width="max-w-2xl">
      <div className="space-y-5" data-testid="deck-generation-modal">
        <div className="rounded-2xl border border-bg-border bg-bg-primary/60 p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
            <Layers3 size={16} />
            最终面板
          </div>
          <p className="mt-2 text-sm leading-6 text-text-secondary">
            选择这次真正负责生成 PPT 成稿的模型面板。系统会用这个面板的模型配置做大纲规划和整稿生成。
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {panels.map((panel, index) => {
              const active = panel.id === selectedPanelId
              return (
                <button
                  key={panel.id}
                  type="button"
                  onClick={() => setSelectedPanelId(panel.id)}
                  className={`rounded-2xl border px-4 py-3 text-left transition-colors ${
                    active
                      ? 'border-accent-blue/40 bg-accent-blue/10'
                      : 'border-bg-border bg-bg-secondary hover:border-accent-blue/25 hover:bg-bg-hover'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium text-text-primary">面板 {index + 1}</span>
                    <span className="text-[11px] uppercase tracking-wide text-text-secondary">
                      {getConnectionTypeLabel(panel.modelConfig)}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-text-primary/90">{panel.modelConfig.model}</p>
                  <p className="mt-1 truncate text-xs text-text-secondary">{panel.modelConfig.base_url}</p>
                </button>
              )
            })}
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_220px]">
          <div className="rounded-2xl border border-bg-border bg-bg-primary/60 p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
              <Database size={16} />
              当前来源模式
            </div>
            <p className="mt-2 text-sm text-text-primary">
              {knowledgeBaseEnabled ? '知识库 + 成功聊天答案' : '仅成功聊天答案'}
            </p>
            <p className="mt-1 text-xs leading-5 text-text-secondary">
              {knowledgeBaseEnabled
                ? '开启知识库时会严格依赖检索结果；证据不足会直接拦截，不再退回纯聊天模式。'
                : '未开启知识库时只会使用成功回答生成主题页，并在成稿里标记为 chat_only。'}
            </p>
          </div>

          <div className="rounded-2xl border border-bg-border bg-bg-primary/60 p-4">
            <label className="text-sm font-medium text-text-primary">目标页数</label>
            <input
              type="number"
              min={4}
              max={10}
              value={targetSlideCount}
              onChange={(event) => {
                const next = Number(event.target.value)
                if (Number.isNaN(next)) return
                setTargetSlideCount(Math.max(4, Math.min(10, next)))
              }}
              className="mt-3 w-full rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent-blue/40"
            />
            <p className="mt-2 text-xs leading-5 text-text-secondary">
              默认 8 页。系统会宁少勿水，内容不足时会自动缩页，不会硬凑空话。
            </p>
          </div>
        </div>

        <div className="rounded-2xl border border-bg-border bg-bg-primary/60 p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
            <Palette size={16} />
            主题模板
          </div>
          <p className="mt-2 text-sm leading-6 text-text-secondary">
            先选定视觉方向，生成后仍可在编辑器里继续切换。
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            {DECK_THEMES.map((theme) => {
              const active = theme.value === selectedTheme
              return (
                <button
                  key={theme.value}
                  type="button"
                  onClick={() => setSelectedTheme(theme.value)}
                  className={`rounded-2xl border px-3 py-3 text-left transition-colors ${
                    active
                      ? 'border-accent-blue/40 bg-accent-blue/10'
                      : 'border-bg-border bg-bg-secondary hover:border-accent-blue/25 hover:bg-bg-hover'
                  }`}
                >
                  <div className={`h-20 rounded-xl border bg-gradient-to-br ${theme.preview}`} />
                  <div className="mt-3 text-sm font-medium text-text-primary">{theme.label}</div>
                  <p className="mt-1 text-xs leading-5 text-text-secondary">{theme.description}</p>
                </button>
              )
            })}
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={submitting}>
            取消
          </Button>
          <Button
            variant="primary"
            onClick={() => void handleSubmit()}
            loading={submitting}
            disabled={!selectedPanel}
            data-testid="deck-generation-submit"
          >
            开始生成
          </Button>
        </div>
      </div>
    </Modal>
  )
}
